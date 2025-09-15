from sqlite3 import IntegrityError
from cola.domain.utils.singleton import singleton

@singleton
class UsersRepository:
    def __init__(self, db_client):
        self.db_client = db_client

    def get_user_password(self, username):
        query = 'SELECT password_hash FROM users WHERE username = ?'
        row = self.db_client.execute_query(query, (username,), fetch_one=True)
        return row

    def create_user(self, username, password):
        try:
            query = 'INSERT INTO users (username, password_hash) VALUES (?, ?)'
            self.db_client.execute_update(query, (username, password))
        except IntegrityError:
            return False, "用户名已存在"
        except Exception as e:
            return False, str(e)