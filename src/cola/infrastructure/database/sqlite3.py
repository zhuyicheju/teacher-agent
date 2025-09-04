import sqlite3
from typing import List, Tuple, Any

from cola.infrastructure.database.dbInterface import DatabaseInterface


class SQLiteClient(DatabaseInterface):
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.connection: sqlite3.Connection | None = None
        self._connect()  # 初始化时建立连接

    def _connect(self) -> None:
        """建立数据库连接"""
        if not self.connection or self.connection.close:
            self.connection = sqlite3.connect(self.db_path)
            # 设置行工厂，方便按列名访问（可选）
            self.connection.row_factory = sqlite3.Row

    def execute_query(self, query: str, params: Tuple[Any, ...] = (), fetch_one = False) -> List[sqlite3.Row]:
        """执行查询并返回结果"""
        try:
            cursor = self.connection.cursor()
            cursor.execute(query, params)
            result = cursor.fetchall() if not fetch_one else cursor.fetchone()
            return result
        except sqlite3.Error as e:
            # 处理异常，可根据需要扩展
            print(f"查询执行失败: {e}")
            raise  # 重新抛出供上层处理
        finally:
            # 对于查询操作，不关闭连接，仅提交（如果有写入操作）
            # 这里保持连接打开以复用
            pass

    def execute_update(self, query: str, params: Tuple[Any, ...] = ()) -> int:
        """执行更新操作（INSERT/UPDATE/DELETE）并返回受影响的行数"""
        try:
            cursor = self.connection.cursor()
            cursor.execute(query, params)
            self.connection.commit()
            return cursor.rowcount
        except sqlite3.Error as e:
            self.connection.rollback()
            print(f"更新执行失败: {e}")
            raise
        finally:
            pass

    def close(self) -> None:
        """关闭数据库连接"""
        if self.connection and not self.connection.close:
            self.connection.close()
            self.connection = None

    def __del__(self) -> None:
        """对象销毁时确保连接关闭"""
        self.close()
