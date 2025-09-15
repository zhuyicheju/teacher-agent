import os
import traceback
from datetime import datetime

from cola.domain.factory.Repositoryfactory import documents_repository, document_segments_repository
from cola.domain.factory.VectorDBFactory import VectorDBFactory
from cola.infrastructure.os.os import os_utils

class VectorDBUtils:
    def delete_vectors(username, thread_id, vector_ids):
        try:
            vdb = VectorDBFactory.get_instances_withoutcreate(username, thread_id)
            if vector_ids:
                vdb.delete_documents(vector_ids)
        except Exception as e:
            print("删除向量失败：", e, traceback.format_exc())

    def delete_vector_dir(username, thread_id):
        # 删除 persist 目录
        try:
            vdb = VectorDBFactory.get_instances_withoutcreate(username=username, thread_id=thread_id)
            persist_dir = getattr(vdb, 'persist_directory', None)
            os_utils.delete_directory(persist_dir)
        except Exception as e:
            print("移除 persist_directory 失败：", e)

    def add_documents(processed_segments, metadatas, thread_id, username, original_filename, filename):
        try:
            # 使用按用户/会话隔离的 VectorDB（传入 username 与 thread_id）
            db = VectorDBFactory.get_instances(username, thread_id)
            # metadata 包含 username、source_file、thread_id 与 segment_index
            # ids 加入 user/thread 信息以便唯一识别
            if thread_id is not None:
                ids = [f"{username}__thread_{thread_id}__{os.path.splitext(filename)[0]}_seg_{i + 1:04d}" for i in
                       range(len(processed_segments))]
            else:
                ids = [f"{username}__{os.path.splitext(filename)[0]}_seg_{i + 1:04d}" for i in
                       range(len(processed_segments))]
            stored_ids = db.add_documents(processed_segments, metadatas=metadatas, ids=ids)

            # 在 users.db 中记录 document 与 segments（包含 thread_id），同时保存 original_filename

            doc_id = documents_repository.insert_documents(username, filename, original_filename,
                                                           datetime.utcnow().isoformat(), len(processed_segments),
                                                           thread_id)

            for idx, vid in enumerate(stored_ids, start=1):
                preview = processed_segments[idx - 1][:200]
                document_segments_repository.add_document_segments(doc_id, idx, vid, preview)
                ##事务

            return doc_id, stored_ids, None

        except Exception as e:
            # 记录完整堆栈到日志，便于排查 VectorDB/Chroma/嵌入相关的问题
            tb = traceback.format_exc()
            print("向量化或写入数据库失败: %s\n%s", str(e), tb)
            vector_error = str(e)
            return None,None,vector_error

vectordb_utils = VectorDBUtils()
