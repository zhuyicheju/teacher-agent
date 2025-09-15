import traceback

from flask import jsonify, request, session
from cola.domain.factory.Repositoryfactory import thread_repository, document_segments_repository, message_repository, documents_repository
from cola.domain.business.threadService import thread_service as thread_domain_service
class ThreadService:
    def __init__(self):
        pass

    def delete_thread(self, thread_id):
        if not session.get('user'):
            return jsonify({'error': '未登录'}), 401
        username = session.get('user')

        # 校验线程归属
        row = thread_repository.verify_thread_ownership(thread_id, username)
        if not row:
            return jsonify({'error': '未找到线程或无权限'}), 404

        return thread_domain_service.delete_thread()


    def thread_list(self):
        if not session.get('user'):
            return jsonify({'error': '未登录'}), 401
        items = thread_domain_service.list_threads(session.get('user'))
        return jsonify({'items': items})

    def create_thread(self):
        if not session.get('user'):
            return jsonify({'error': '未登录'}), 401
        data = request.get_json(silent=True) or request.form
        title = (data.get('title') or '').strip()

        tid = thread_domain_service.create_thread(session.get('user'), title)
        return jsonify({'thread_id': tid})

    def thread_messages(self, thread_id):
        if not session.get('user'):
            return jsonify({'error': '未登录'}), 401

        msgs = thread_domain_service.get_thread_messages(session.get('user'), thread_id)

        if msgs is None:
            return jsonify({'error': '未找到线程或无权限'}), 404
        return jsonify({'messages': msgs})

thread_service = ThreadService()