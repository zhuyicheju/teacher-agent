import json

from flask import jsonify, Response

from cola.domain.business.ragAgent import rag_answer_stream
from cola.domain.business.threadService import thread_service
from cola.domain.factory.Repositoryfactory import thread_repository, message_repository
from cola.infrastructure.externalServer.zhipuServer import zhipu_server


class ChatService:

    def create_event_stream_response(self, question, username, thread_id, generated_title):
        """创建事件流响应生成器"""
        def generate():
            full_response = ''
            try:

                for content in rag_answer_stream(
                        question, username=username, top_k=5, thread_id=thread_id
                ):
                    full_response += content
                    yield f"data: {json.dumps({'content': content})}\n\n"

                message_repository.add_message(thread_id, username, 'assistant', full_response)

                meta = {'thread_id': thread_id}
                if generated_title:
                    meta['title'] = generated_title
                yield f"data: {json.dumps({'meta': meta})}\n\n"
                yield "data: [DONE]\n\n"

            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                yield "data: [DONE]\n\n"

        return Response(generate(), mimetype='text/event-stream')

    def handle_thread_and_message(
                self, username, question, thread_id
            ):

        if not thread_id:

            thread_id = thread_service.create_thread(username, '')

            self._save_user_message(thread_id, username, question)
            generate_title = self._generate_and_update_thread_title(thread_id, question)

        else:
            thread_id = int(thread_id)
            # 校验线程归属
            if not thread_repository.thread_belongs_to_user(thread_id, username):
                return jsonify({'error': '未找到线程或无权限'}), 404
            message_repository.add_message(thread_id, username, 'user', question)

    def _save_user_message(self, thread_id, username, question):
        """保存用户消息到数据库"""
        try:
            if not thread_repository.thread_belongs_to_user(thread_id, username):
                raise ValueError("线程不存在或不属于当前用户")
            message_repository.add_message(thread_id, username, 'user', question)
        except Exception as e:
            print("保存用户消息失败：", e)

    def _generate_and_update_thread_title(self, thread_id, question):
        """生成并更新线程标题"""
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
        return generated_title

chat_service = ChatService()