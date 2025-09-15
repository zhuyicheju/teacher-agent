import traceback

from flask import jsonify

from cola.domain.factory.Repositoryfactory import thread_repository, document_segments_repository, message_repository, \
    documents_repository
from cola.domain.factory.VectorDBFactory import VectorDBFactory
from cola.infrastructure.vectordb.vectorDButils import vectordb_utils
from cola.infrastructure.os.os import os_utils

class ThreadService:
    def create_thread(username: str, title: str = None) -> int:
        thread_id = thread_repository.create_thread(username, title)
        VectorDBFactory.create_instance(username, thread_id)

        return thread_id

    def get_thread_messages(username: str, thread_id: int):
        if not thread_repository.thread_belongs_to_user(thread_id, username):
            return None

        rows = thread_repository.get_thread_messages(username, thread_id)

        return [{'id': r[0], 'role': r[1], 'content': r[2], 'created_at': r[3]} for r in rows]

    def list_threads(username: str, limit: int = 100):
        rows = thread_repository.list_threads(username, limit)
        return [{'id': r[0], 'title': r[1], 'created_at': r[2]} for r in rows]

    def delete_thread(username: str, thread_id: int):
        try:
            # 获取该线程下的所有文档 id
            rows = thread_repository.get_documents(thread_id, username)
            docs = [r[0] for r in rows]

            # 收集所有 vector_id
            rows = document_segments_repository.get_vector_ids_by_docs(docs)
            vector_ids = [r[0] for r in rows if r and r[0]]

            vectordb_utils.delete_vectors(username, vector_ids)


            vectordb_utils.delete_vector_dir(username, vector_ids)


            # 删除 raw_documents 目录下该线程的源文件
            os_utils.delete_directory(username, thread_id)

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


thread_service = ThreadService()