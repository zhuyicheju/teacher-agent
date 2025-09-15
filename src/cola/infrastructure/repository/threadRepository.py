from datetime import datetime

from cola.domain.utils.singleton import singleton

@singleton
class ThreadRepository:
    def __init__(self, db_client):
        self.db_client = db_client

    def list_threads(self, username=None, limit = 100):
        """查询所有线程并按ID倒序排列"""
        query = '''
            SELECT id, title, created_at 
            FROM threads 
            WHERE (? IS NULL OR username = ?)
            ORDER BY id DESC 
            LIMIT ?
        '''

        rows = self.db_client.execute_query(query, (username, limit))
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

    def create_thread(self, username, title):
        query = 'INSERT INTO threads (username, title, created_at) VALUES (?, ?, ?)'
        thread_id = self.db_client.execute_update(query, (username,  (username, title or '', datetime.utcnow().isoformat())))
        return thread_id

    def thread_belongs_to_user(self, thread_id: int, username: str) -> bool:
        query = 'SELECT 1 FROM threads WHERE id = ? AND username = ?'
        rows = self.db_client.execute_query(query, (thread_id, username))
        ok = rows is not None
        return ok

    def update_thread_title(self, thread_id: int, title: str):
        query = 'UPDATE threads SET title = ? WHERE id = ?'
        self.db_client.execute_update(query, (title, thread_id))
