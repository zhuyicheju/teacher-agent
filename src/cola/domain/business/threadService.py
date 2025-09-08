from cola.domain.factory.Repositoryfactory import thread_repository
from cola.domain.factory.VectorDBFactory import VectorDBFactory

class ThreadService:
    def create_thread(username: str, title: str = None) -> int:
        thread_id = thread_repository.create_thread(username, title)
        VectorDBFactory.create_instance(username, thread_id)

        return thread_id

    def get_thread_messages(username: str, thread_id: int):
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute('SELECT id FROM threads WHERE id = ? AND username = ?', (thread_id, username))
        if not cur.fetchone():
            conn.close()
            return None
        cur.execute(
            'SELECT id, role, content, created_at FROM messages WHERE thread_id = ? AND username = ? ORDER BY id ASC',
            (thread_id, username))
        rows = cur.fetchall()
        conn.close()
        return [{'id': r[0], 'role': r[1], 'content': r[2], 'created_at': r[3]} for r in rows]

    def list_threads(username: str, limit: int = 100):
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute('SELECT id, title, created_at FROM threads WHERE username = ? ORDER BY id DESC LIMIT ?', (username, limit))
        rows = cur.fetchall()
        conn.close()
        return [{'id': r[0], 'title': r[1], 'created_at': r[2]} for r in rows]


thread_service = ThreadService()