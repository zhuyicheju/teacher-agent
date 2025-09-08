from typing import Tuple, Dict

from cola.infrastructure.vectordb.vectordb import VectorDB

class VectorDBFactory:
    """VectorDB 工厂类，管理不同 (username, thread_id) 的实例"""
    # 缓存键：(username, thread_id) 元组，值为对应的 VectorDB 实例
    _instances: Dict[Tuple[str, int], VectorDB] = {}

    @classmethod
    def create_instance(cls, username: str, thread_id: int,
                       persist_directory: str, collection_name: str) -> VectorDB:
        """
        创建并缓存实例（若已存在则覆盖）
        :param username: 用户标识（可选）
        :param thread_id: 线程标识（可选）
        :param persist_directory: 持久化目录（可选，传给 VectorDB）
        :param collection_name: 集合名称（可选，传给 VectorDB）
        :return: 创建的 VectorDB 实例
        """
        cache_key = (username, thread_id)
        # 创建新实例并覆盖缓存（若已存在）
        instance = VectorDB(
            username=username,
            thread_id=thread_id,
            persist_directory=persist_directory,
            collection_name=collection_name
        )
        cls._instances[cache_key] = instance
        return instance

    @classmethod
    def get_instance(cls, username: str, thread_id: int, persist_directory, collection_name) -> VectorDB:
        """
        获取缓存的实例（不存在则返回 None）
        :param username: 用户标识（需与创建时一致）
        :param thread_id: 线程标识（需与创建时一致）
        :return: 缓存的 VectorDB 实例或 None
        """
        cache_key = (username, thread_id)
        vector_db = cls._instances.get(cache_key)
        if vector_db is None:
            return cls.create_instance(username, thread_id, persist_directory, collection_name)
        return vector_db

    @classmethod
    def get_instances_withoutcreate(cls, username: str, thread_id: int):
        cache_key = (username, thread_id)
        vector_db = cls._instances.get(cache_key)
        if vector_db is None:
            raise ValueError(f"没有找到 username: {username}, thread_id: {thread_id} 对应的实例")
        return vector_db