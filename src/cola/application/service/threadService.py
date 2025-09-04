import traceback

from flask import jsonify, request, session
from cola.domain.factory.Repositoryfactory import thread_repository, document_segments_repository, message_repository, documents_repository

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

        try:
            # 获取该线程下的所有文档 id
            rows = thread_repository.get_documents(thread_id, username)
            docs = [r[0] for r in rows]

            # 收集所有 vector_id
            rows = document_segments_repository.get_vector_ids_by_docs(docs)
            vector_ids = [r[0] for r in rows if r and r[0]]

            # 删除向量（在对应命名空间/collection）
            try:
                vdb = VectorDB(username=username, thread_id=thread_id)
                if vector_ids:
                    vdb.delete_documents(vector_ids)
            except Exception as e:
                # 记录但不阻塞后续删除
                print("删除向量失败：", e, traceback.format_exc())

            # 尝试移除 Chroma 持久化目录（彻底清除会话知识库数据）
            try:
                vdb = VectorDB(username=username, thread_id=thread_id)
                persist_dir = getattr(vdb, 'persist_directory', None)
                if persist_dir and os.path.isdir(persist_dir):
                    shutil.rmtree(persist_dir, ignore_errors=True)
            except Exception as e:
                print("移除 persist_directory 失败：", e)

            # 删除 raw_documents 目录下该线程的源文件
            try:
                raw_dir = os.path.abspath(
                    os.path.join(base_dir, 'data', 'raw_documents', username, f"thread_{thread_id}"))
                if os.path.isdir(raw_dir):
                    shutil.rmtree(raw_dir, ignore_errors=True)
            except Exception as e:
                print("移除 raw_documents 失败：", e)

            ##事务
            # 在事务中删除 DB 中的 messages、document_segments、documents、threads
            try:
                message_repository.delete_messages(thread_id, username)
                if docs:
                    document_segments_repository.delete_segments_by_docs(docs)
                    documents_repository.delete_documents(docs)

                thread_repository.delete_thread(thread_id, username)
            except Exception as e:
                print("删除数据库记录失败：", e, traceback.format_exc())
                return jsonify({'error': f'删除数据库记录失败: {e}'}), 500

        except Exception as e:
            print("删除线程过程中出错：", e, traceback.format_exc())
            return jsonify({'error': str(e)}), 500

        return jsonify({'success': True})

    def thread_list(self):
        if not session.get('user'):
            return jsonify({'error': '未登录'}), 401
        items = list_threads(session.get('user'))
        return jsonify({'items': items})

    def create_thread(self):
        if not session.get('user'):
            return jsonify({'error': '未登录'}), 401
        data = request.get_json(silent=True) or request.form
        title = (data.get('title') or '').strip()
        tid = create_thread(session.get('user'), title)
        return jsonify({'thread_id': tid})

    def thread_messages(self, thread_id):
        if not session.get('user'):
            return jsonify({'error': '未登录'}), 401
        msgs = get_thread_messages(session.get('user'), thread_id)
        if msgs is None:
            return jsonify({'error': '未找到线程或无权限'}), 404
        return jsonify({'messages': msgs})

thread_service = ThreadService()