from cola.domain.utils.singleton import singleton

@singleton
class DocumentsRepository():
    def __init__(self, db_client):
        self.db_client = db_client

    def list_documents(self, username, thread_id):
        query = """SELECT id, username, COALESCE(original_filename, filename), stored_at, segment_count, thread_id 
                   FROM documents"""
        conds = []
        params = []
        if username:
            conds.append('username = ?');
            params.append(username)
        if thread_id is not None:
            conds.append('thread_id = ?');
            params.append(thread_id)
        if conds:
            query += ' WHERE ' + ' AND '.join(conds)
        query += ' ORDER BY id DESC'
        rows = self.db_client.execute(query, params)
        return rows

    def delete_documents(self, doc_ids):
        """批量删除文档"""
        if not doc_ids:
            return
        placeholders = ", ".join(["?"] * len(doc_ids))
        query = f"DELETE FROM documents WHERE id IN ({placeholders})"
        self.db_client.execute_update(query, doc_ids)

    def get_document_info(self, doc_id: int) -> Optional[Tuple]:
        """根据文档ID查询文档信息（id, username, filename, thread_id）"""
        query = "SELECT id, username, filename, thread_id FROM documents WHERE id = ?"
        row = self.db_client.execute_query(query, (doc_id,), fetch_one=True)
        return row

    def insert_documents(self, username, filename, original_filename, stored_at, segment_count, thread_id):
        query = """INSERT INTO documents (username, filename, original_filename, stored_at, segment_count, thread_id)
                    VALUES (?, ?, ?, ?, ?, ?)"""
        rowcount = self.db_client.execute_update(query,
                                     (username, filename, original_filename, stored_at, segment_count, thread_id))
        return rowcount

    def get_documents(self, thread_id, username):
        """获取该线程下所有文档ID"""
        query = 'SELECT id FROM documents WHERE thread_id = ? AND username = ?'
        rows = self.db_client.fetch_all(query, (thread_id, username))
        return rows