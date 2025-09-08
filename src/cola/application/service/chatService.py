import json

from flask import session, jsonify, request, Response
from cola.domain.business.threadService import thread_service
from cola.domain.factory.Repositoryfactory import message_repository, thread_repository
from cola.infrastructure.externalServer.zhipuServer import zhipu_server

class ChatService:
    def __init__(self):
        pass

    def ask(self):
        # 后端再做一次登录校验（防止直接访问）
        if not session.get('user'):
            return jsonify({'error': '未登录，请先登录'}), 401

        username = session.get('user')

        try:
            if request.method == 'POST':
                data = request.get_json() or {}
                question = data.get('question', '')
                thread_id = data.get('thread_id')
            else:
                question = request.args.get('question', '')
                thread_id = request.args.get('thread_id')

            if not question:
                return jsonify({'error': '问题不能为空'}), 400

            # 如果没有提供 thread_id 则自动新建一个线程（先空标题，后由大模型生成并更新）
            if not thread_id:
                # 先创建线程，空标题
                thread_id = thread_service.create_thread(username, '')
                # 保存用户提问为消息（先保存，标题生成不影响消息）
                try:
                    if not thread_repository.thread_belongs_to_user(thread_id, username):
                        raise ValueError("线程不存在或不属于当前用户")
                    message_repository.add_message(thread_id, username, 'user', question)
                except Exception as e:
                    print("保存用户消息失败：", e)

                # 使用大模型对第一个问题生成简短会话标题
                generated_title = ''
                try:
                    generated_title = zhipu_server.generate_title_sync(question, top_k=1)
                    generated_title = (generated_title or '').strip().replace('\n', ' ')
                    if generated_title:
                        # 截断为合理长度
                        if len(generated_title) > 80:
                            generated_title = generated_title[:80].rstrip() + '...'
                        thread_repository.update_thread_title(thread_id, generated_title)
                except Exception as e:
                    print('生成会话标题失败：', e)

            else:
                thread_id = int(thread_id)
                # 校验线程归属
                if not thread_repository.thread_belongs_to_user(thread_id, username):
                    return jsonify({'error': '未找到线程或无权限'}), 404
                message_repository.add_message(thread_id, username, 'user', question)

            # 如果已存在生成的标题但前端/列表尚未刷新，会在后续 loadThreads 时显示新标题
            def generate():
                full_response = ''
                try:
                    # 将 thread_id 传入 rag_answer_stream，要求 rag_agent 根据 thread_id 使用该会话的独立知识库
                    for content in rag_answer_stream(question, username=username, top_k=5, thread_id=thread_id):
                        full_response += content
                        yield f"data: {json.dumps({'content': content})}\n\n"
                    message_repository.add_message(thread_id, username, 'assistant', full_response)
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

    def generate_title(self):
        """
        POST /generate_title
        Body JSON: { "question": "...", "thread_id": optional }
        返回: { "title": "...", "thread_id": 123 }
        会将生成的标题写入 threads 表的 title 字段以便刷新后持久显示。
        """
        if not session.get('user'):
            return jsonify({'error': '未登录'}), 401

        data = request.get_json(silent=True) or request.form or {}
        question = (data.get('question') or '').strip()
        thread_id = data.get('thread_id')

        if not question:
            return jsonify({'error': 'question 不能为空'}), 400

        try:
            if thread_id is not None and str(thread_id).strip() != '':
                try:
                    thread_id = int(thread_id)
                except Exception:
                    return jsonify({'error': 'thread_id 格式错误'}), 400
                # 校验归属
                if not _thread_belongs_to_user(thread_id, session.get('user')):
                    return jsonify({'error': '线程不存在或不属于当前用户'}), 403
            else:
                # 未提供 thread_id，则选择该用户最近的线程
                thread_id = _find_latest_thread_for_user(session.get('user'))
                if thread_id is None:
                    return jsonify({'error': '未找到可更新标题的线程'}), 404

            # 生成标题：使用同步接口 generate_title_sync（不使用流式 rag_answer_stream）
            title = generate_title_sync(question, username=session.get('user'), thread_id=thread_id, top_k=1)
            title = (title or '').strip().replace('\n', ' ')

            if title:
                if len(title) > 120:
                    title = title[:120].rstrip() + '...'
                # 写入数据库以永久保存
                try:
                    _update_thread_title(thread_id, title)
                except Exception as e:
                    # 写入失败仍返回生成的标题，但给出警告
                    return jsonify({'title': title, 'thread_id': thread_id, 'warning': f'更新数据库失败: {e}'}), 200

                return jsonify({'title': title, 'thread_id': thread_id}), 200
            else:
                return jsonify({'error': '模型未生成标题'}), 500

        except Exception as e:
            tb = traceback.format_exc()
            # 记录到服务器日志以便排查（此处仅返回简短错误）
            print('generate_title error:', e, tb)
            return jsonify({'error': '生成标题失败', 'detail': str(e)}), 500


chat_service = ChatService()