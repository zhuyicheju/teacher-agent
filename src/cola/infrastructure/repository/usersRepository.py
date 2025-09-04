from cola.domain.utils.singleton import singleton

@singleton
class UsersRepository:
    def __init__(self, db_client):
        self.db_client = db_client