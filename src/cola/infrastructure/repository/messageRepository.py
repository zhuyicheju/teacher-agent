from datetime import datetime

from cola.domain.utils.singleton import singleton

@singleton
class MessageRepository:
    def __init__(self, db_client):
        self.db_client = db_client

    def delete_messages(self, thread_id, username) -> None:
        """删除指定线程下的所有消息"""
        query = "DELETE FROM messages WHERE thread_id = ? AND username = ?"
        self.db_client.execute_update(query, (thread_id, username))

    def add_message(self, thread_id: int, username: str, role: str, content: str):
        query = 'INSERT INTO messages (thread_id, username, role, content, created_at) VALUES (?, ?, ?, ?, ?)'
        self.db_client.execute_update(query,thread_id, (username, role, content, datetime.utcnow().isoformat()))

    def get_thread_messages(self, thread_id, username):
        query = 'SELECT id, role, content, created_at FROM messages WHERE thread_id = ? AND username = ? ORDER BY id ASC'
        rows = self.db_client.execute_query(query, (thread_id, username))
        return rows