from cola.infrastructure import config
from cola.infrastructure.database.dbInterface import DatabaseInterface
from cola.infrastructure.database.sqlite3 import SQLiteClient
from cola.infrastructure.repository.threadRepository import ThreadRepository
from cola.infrastructure.repository.documentsRepository import DocumentsRepository
from cola.infrastructure.repository.usersRepository import UsersRepository
from cola.infrastructure.repository.documentSegmentsRepository import DocumentSegmentRepository
from cola.infrastructure.repository.messageRepository import MessageRepository
class RepositoryFactory:
    """仓储工厂，负责创建和管理所有Repository的单例实例"""

    def __init__(self):
        self.db_client = SQLiteClient(config.DB_DIR)

        self._init_repositories()

    def _init_repositories(self):
        """初始化所有仓储实例"""
        self.thread_repo = ThreadRepository(self.db_client)
        self.documents_repo = DocumentsRepository(self.db_client)
        self.users_repo = UsersRepository(self.db_client)
        self.document_segments_repo = DocumentSegmentRepository(self.db_client)
        self.message_repo = MessageRepository(self.db_client)

repo_factory = RepositoryFactory()

thread_repository = repo_factory.thread_repo
users_repository = repo_factory.users_repo
documents_repository = repo_factory.documents_repo
document_segments_repository = repo_factory.document_segments_repo
message_repository = repo_factory.message_repo