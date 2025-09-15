import traceback
from datetime import datetime

from flask import jsonify
from werkzeug.utils import secure_filename

from cola.domain.utils.document import read_document, split_document
from cola.domain.factory.Repositoryfactory import documents_repository, document_segments_repository
from cola.infrastructure.os.os import os_utils
from cola.infrastructure.vectordb.vectorDButils import vectordb_utils


ALLOWED_EXTENSIONS = {'pdf', 'docx'}

class DocumentService:
    def list_user_document_titles(username: str, limit: int = 100, thread_id: int = None):
        """
        返回指定用户的文档标题列表（仅标题/文件名、文档 id 与所属 thread）。
        若提供 thread_id 则只返回该会话下的文档（实现会话级知识隔离）。
        """
        if thread_id is None:
            rows = documents_repository.list_titles_without_threadid(username, limit)
        else:
            rows = documents_repository.list_titles_without_threadid(username, thread_id, limit)

        return [{'id': r[0], 'title': r[1], 'thread_id': r[2]} for r in rows]

    def list_user_documents(username: str, limit: int = 100, thread_id: int = None):
        if thread_id is None:
            # 未指定 thread_id 时，查询所有文件，返回时使用 original_filename（回退到 filename）
            rows = documents_repository.list_titles_without_threadid(username, limit)
        else:
            rows = documents_repository.list_titles_with_threadid(username, thread_id,limit)
            # 指定 thread_id 时，仅查询该会话的文件

        return [{'id': r[0], 'filename': r[1], 'stored_at': r[2], 'segment_count': r[3], 'thread_id': r[4]} for r in
                rows]

    def get_document_segments(username: str, document_id: int):
        # 验证文档属于该用户
        if not documents_repository.document_belong_to_user():
            return None
        rows = documents_repository.get_document_segments(document_id)
        return [{'index': r[0], 'vector_id': r[1], 'preview': r[2]} for r in rows]

    def process_uploaded_document(file_path: str):
        content = read_document(file_path)
        if not content or not content.strip():
            raise ValueError("读取的文档内容为空，无法分割")
        return split_document(content)

    def delete_document(self, username, doc_id, filename):
        ##这些数据库操作都得组成一个事务
        try:
            # 获取该文档的所有 vector_id
            rows = document_segments_repository.get_vector_ids_by_docs(doc_id)
            vector_ids = [r[0] for r in rows if r and r[0]]

            row = documents_repository.find_thread_id_with_doc_id(doc_id)
            if row is None:
                raise "未找到文档对应的线程"
            thread_id = row[0]["thread_id"]

            vectordb_utils.delete_vectors(username, thread_id, vector_ids)

            document_segments_repository.delete_segments_by_doc(doc_id)
            documents_repository.delete_documents(doc_id)

        except Exception as e:
            return jsonify({'error': str(e)}), 500

        os_utils.delete_document(username, doc_id, basedir)

        return jsonify({'success': True})

    def upload_document(self, username, file, thread_id):

        # 保存原始文件名（未经 secure_filename 改写）
        original_filename = file.filename

        filename = secure_filename(file.filename)
        if not self._allowed_file(filename):
            return jsonify({"error": f"不支持的文件类型，仅支持: {', '.join(sorted(self.ALLOWED_EXTENSIONS))}"}), 400

        file_path = os_utils.upload_document(username, thread_id, file, filename)

        try:
            processed_segments = document_segments_repository.process_uploaded_document(file_path)
        except Exception as e:
            tb = traceback.format_exc()
            print("读取或分割文档失败: %s\n%s", str(e), tb)
            return jsonify({"error": "读取或分割文档失败", "detail": str(e)}), 500

        metadatas = [
            {"username": username, "source_file": original_filename, "thread_id": thread_id, "segment_index": i + 1} for
            i in range(len(processed_segments))]

        (doc_id, stored_ids, vector_error) = add_documents(processed_segments, metadatas, thread_id, username, original_filename, filename)

        # 根据是否创建了 documents 记录返回 success 标志与文档信息
        success = doc_id is not None
        document_info = None
        if success:
            # 返回给前端的 filename 字段使用原始文件名（未被 secure_filename 改写）
            document_info = {
                "id": doc_id,
                "username": username,
                "filename": original_filename,
                "stored_at": datetime.utcnow().isoformat(),
                "segment_count": len(processed_segments),
                "thread_id": thread_id
            }

        # 若在向量化阶段出现错误，返回 500 并携带 vector_error（前端可显示给开发人员）
        status_code = 200 if success else 500
        resp = {
            "success": success,
            "message": "上传完成" if success else "上传失败（详见 vector_error 或后端日志）",
            "document": document_info,
            "segments": processed_segments,
            "stored_ids": stored_ids,
            "vector_error": vector_error
        }

        return jsonify(resp), status_code

    def _allowed_file(self, filename):
        if not filename or '.' not in filename:
            return False
        ext = filename.rsplit('.', 1)[1].lower()
        return ext in ALLOWED_EXTENSIONS

document_service = DocumentService()