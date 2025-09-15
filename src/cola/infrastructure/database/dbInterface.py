from abc import ABC, abstractmethod
from typing import List, Tuple, Any


class DatabaseInterface(ABC):
    """数据库操作抽象接口，定义所有数据库操作的标准方法"""

    @abstractmethod
    def connect(self) -> None:
        """建立数据库连接"""
        pass

    @abstractmethod
    def close(self) -> None:
        """关闭数据库连接"""
        pass

    @abstractmethod
    def execute_query(self, query: str, params: Tuple[Any, ...] = None) -> List[Tuple[Any, ...]]:
        """
        执行查询语句

        :param query: SQL查询语句
        :param params: 查询参数
        :return: 查询结果列表
        """
        pass

    @abstractmethod
    def execute_update(self, query: str, params: Tuple[Any, ...] = None) -> int:
        """
        执行更新语句(INSERT/UPDATE/DELETE)

        :param query: SQL更新语句
        :param params: 更新参数
        :return: 受影响的行数
        """
        pass
