from flask import jsonify

from cola.domain.factory.Repositoryfactory import documents_repository, document_segments_repository, \
    message_repository, thread_repository
from cola.infrastructure.os.os import get_raw_dir, delete_directory
from cola.infrastructure.vectordb.vectorDButils import delete_vectors, delete_vector_dir


class AdminService:

    def delete_thread(self, username, thread_id):
        try:
            row = documents_repository.list_documents(username, thread_id)
            docs = [r[0] for r in row]

            row = document_segments_repository.get_vector_ids_by_docs(docs)
            vector_ids = [r[0] for r in row if r and r[0]]

            delete_vectors(username, thread_id, vector_ids)

            delete_vector_dir(username, thread_id)

            # 删除 raw_documents
            try:
                raw_dir = get_raw_dir(username, thread_id)
                delete_directory(raw_dir)
            except Exception as e:
                print("管理员移除 raw_documents 失败：", e)

            # 删除 DB 记录
            try:
                message_repository.delete_message_repository(thread_id)
                if docs:
                    document_segments_repository.delete_segments_by_docs(docs)
                    documents_repository.delete_documents(docs)
                thread_repository.delete_thread(thread_id)
                ## 组合成事务
            except Exception as e:
                ##回滚
                return jsonify({'error': f'删除数据库记录失败: {e}'}), 500

        except Exception as e:
            ## 回滚
            return jsonify({'error': str(e)}), 500

    def delete_documents(self, doc_id):
        row = documents_repository.get_document_info(doc_id)
        if not row:
            return jsonify({'error': '未找到该文档'}), 404
        owner = row[1]
        doc_thread = row[3]

        try:
            rows = document_segments_repository.get_vector_ids_by_docs(doc_thread)
            vector_ids = [r[0] for r in rows if r and r[0]]

            delete_vectors(owner, doc_thread, vector_ids)

            document_segments_repository.delete_segments_by_doc(doc_id)
            documents_repository.delete_documents(doc_id)
        except Exception as e:
            return jsonify({'error': str(e)}), 500


        raw_file = get_raw_files(owner, doc_thread, row[2])
        delete_files(raw_file)

admin_service = AdminService()