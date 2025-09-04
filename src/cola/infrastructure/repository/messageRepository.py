from cola.domain.utils.singleton import singleton

@singleton
class MessageRepository:
    def __init__(self, db_client):
        self.db_client = db_client

    def delete_messages(self, thread_id, username) -> None:
        """删除指定线程下的所有消息"""
        query = "DELETE FROM messages WHERE thread_id = ? AND username = ?"
        self.db_client.execute_update(query, (thread_id, username))