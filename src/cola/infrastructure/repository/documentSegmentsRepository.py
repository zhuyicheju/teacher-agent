from cola.domain.utils.singleton import singleton

@singleton
class DocumentSegmentRepository:
    def __init__(self, db_client):
        self.db_client = db_client

    def get_vector_ids_by_docs(self, doc_ids):
        """根据文档ID列表查询关联的向量ID"""
        if not doc_ids:
            return []
        placeholders = ", ".join(["?"] * len(doc_ids))
        query = f"SELECT vector_id FROM document_segments WHERE document_id IN ({placeholders})"
        rows = self.db_client.execute_query(query, doc_ids)
        return rows

    def delete_segments_by_docs(self, doc_ids):
        """根据文档ID列表删除关联的片段"""
        if not doc_ids:
            return
        placeholders = ", ".join(["?"] * len(doc_ids))
        query = f"DELETE FROM document_segments WHERE document_id IN ({placeholders})"
        self.db_client.execute_update(query, doc_ids)

    def delete_segments_by_doc(self, doc_id: int) -> None:
        """根据文档ID删除关联的片段"""
        query = "DELETE FROM document_segments WHERE document_id = ?"
        self.db_client.execute_update(query, (doc_id))

    def add_document_segments(self, doc_id, idx, vid, preview):
        query = "INSERT INTO document_segments (document_id, segment_index, vector_id, preview) VALUES (?, ?, ?, ?)"
        self.db_client.execute_update(query, ((doc_id, idx, vid, preview)))
