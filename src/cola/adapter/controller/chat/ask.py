from flask import Blueprint, jsonify, session, request

bp_ask = Blueprint("ask", __name__)

@bp_ask.route('/ask', methods=['POST', 'GET'])
def ask_stream():
    # 后端再做一次登录校验（防止直接访问）
    if not session.get('user'):
        return jsonify({'error': '未登录，请先登录'}), 401

    try:
        username = session.get('user')
        if request.method == 'POST':
            data = request.get_json() or {}
            question = data.get('question', '')
            thread_id = data.get('thread_id')  # 支持 POST 指定 thread
        else:
            question = request.args.get('question', '')
            thread_id = request.args.get('thread_id')  # 支持 GET(EventSource) 指定 thread

        if not question:
            return jsonify({'error': '问题不能为空'}), 400

        # 如果没有提供 thread_id 则自动新建一个线程（先空标题，后由大模型生成并更新）
        generated_title = ''
        if not thread_id:
            # 先创建线程，空标题
            thread_id = create_thread(username, '')
            # 保存用户提问为消息（先保存，标题生成不影响消息）
            try:
                add_message(thread_id, username, 'user', question)
            except Exception as e:
                print("保存用户消息失败：", e)

            # 使用大模型对第一个问题生成简短会话标题
            try:
                generated_title = generate_title_sync(question, username=username, thread_id=thread_id, top_k=1)
                generated_title = (generated_title or '').strip().replace('\n', ' ')
                if generated_title:
                    # 截断为合理长度
                    if len(generated_title) > 80:
                        generated_title = generated_title[:80].rstrip() + '...'
                    update_thread_title(thread_id, generated_title)
            except Exception as e:
                print('生成会话标题失败：', e)
        else:
            try:
                thread_id = int(thread_id)
            except Exception:
                return jsonify({'error': 'thread_id 格式错误'}), 400
            # 校验线程归属
            if not thread_belongs_to_user(thread_id, username):
                return jsonify({'error': '未找到线程或无权限'}), 404
            # 保存用户提问
            try:
                add_message(thread_id, username, 'user', question)
            except Exception as e:
                print("保存用户消息失败：", e)

        # 如果已存在生成的标题但前端/列表尚未刷新，会在后续 loadThreads 时显示新标题
        def generate():
            full_response = ''
            try:
                # 将 thread_id 传入 rag_answer_stream，要求 rag_agent 根据 thread_id 使用该会话的独立知识库
                for content in rag_answer_stream(question, username=username, top_k=5, thread_id=thread_id):
                    full_response += content
                    yield f"data: {json.dumps({'content': content})}\n\n"
                # 保存助手回答为消息
                try:
                    add_message(thread_id, username, 'assistant', full_response)
                except Exception as e:
                    print("保存助手消息失败：", e)
                # 返回 thread_id 与可能的标题（以便前端在需要时更新显示）
                meta = {'thread_id': thread_id}
                if generated_title:
                    meta['title'] = generated_title
                yield f"data: {json.dumps({'meta': meta})}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                yield "data: [DONE]\n\n"

        return Response(generate(), mimetype='text/event-stream')

    except Exception as e:
        print("错误信息:", e)
        return jsonify({'error': '服务器内部错误，请稍后再试！'}), 500
