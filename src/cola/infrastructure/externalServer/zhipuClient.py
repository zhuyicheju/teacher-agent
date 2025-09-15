import re
from typing import Optional, Any
from zhipuai import ZhipuAI  # 假设这是官方SDK


class ZhipuClient:
    """ZhipuAI客户端，负责处理API调用，实现单例模式"""
    _instance: Optional['ZhipuClient'] = None

    def __new__(cls, api_key: Optional[str] = None):
        """单例模式，确保只创建一个实例"""
        if cls._instance is None:
            if not api_key:
                raise ValueError("API key must be provided for initial creation")
            cls._instance = super().__new__(cls)
            cls._instance._client = ZhipuAI(api_key=api_key)
        return cls._instance

    @classmethod
    def get_instance(cls) -> 'ZhipuClient':
        """获取客户端实例"""
        if cls._instance is None:
            raise RuntimeError("ZhipuClient has not been initialized. Call constructor first.")
        return cls._instance

    def chat_sync(
            self,
            model: str,
            messages: list[dict[str, str]],
    ) :
        """调用聊天补全API"""
        return self._client.chat.completions.create(
            model=model,
            messages=messages,
            stream=False
        )

    def chat_stream(cls, model: str, messages: list):
        """流式聊天接口"""
        return cls.get_instance().chat.completions.create(
            model=model,
            messages=messages,
            stream=True
        )

zhipu_client = ZhipuClient(api_key="98ed0ed5a81f4a958432644de29cb547.LLhUp4oWijSoizYc")