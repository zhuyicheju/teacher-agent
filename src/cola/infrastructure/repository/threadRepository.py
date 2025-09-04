from cola.domain.utils.singleton import singleton

@singleton
class ThreadRepository:
    def __init__(self, db_client):
        self.db_client = db_client

    def list_threads(self):
        """查询所有线程并按ID倒序排列"""
        query = """
            SELECT id, username, title, created_at 
            FROM threads 
            ORDER BY id DESC
        """
        rows = self.db_client.execute_query(query)
        return rows

    def get_thread_username(self, thread_id: int):
        """根据线程ID查询所属用户名"""
        query = "SELECT username FROM threads WHERE id = ?"
        row = self.db_client.execute_query(query, (thread_id,), fetch_one=True)
        return row

    def delete_thread(self, thread_id: int):
        """删除指定ID的线程"""
        query = "DELETE FROM threads WHERE id = ?"
        self.db_client.execute_update(query, (thread_id,))

    def verify_thread_ownership(self, thread_id, username):
        """验证线程归属"""
        query = "SELECT 1 FROM threads WHERE id = ? AND username = ?"
        row = self.db_client.execute_query(query, (thread_id, username), fetch_one=True)
        return row

    def get_documents(self, thread_id, username):
        """获取该线程下所有文档ID"""
        query = 'SELECT id FROM documents WHERE thread_id = ? AND username = ?'
        rows = self.db_client.fetch_all(query, (thread_id, username))
        return rows