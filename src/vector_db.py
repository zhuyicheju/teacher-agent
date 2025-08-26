import os
import uuid
from typing import List, Optional, Dict, Any

# 必要模块位置
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DEFAULT_PERSIST_DIR = os.path.join(PROJECT_ROOT, 'knowledge_base', 'chroma_db')


class VectorDB:
    """
    将文本块生成向量并保存到 Chroma。
    配置与调用已写死为 ZhipuAI（API Key 硬编码）。
    兼容多版本 chromadb 的 client/collection 构造与 upsert/add 方法。
    """

    def __init__(self, persist_directory: Optional[str] = None, collection_name: str = "teacher_agent"):
        self.persist_directory = persist_directory or DEFAULT_PERSIST_DIR
        self.collection_name = collection_name
        self._client = None
        self._collection = None
        self._embedder = None
        self._embed_model = "embedding-2"
        os.makedirs(self.persist_directory, exist_ok=True)

    def _init_chroma(self):
        if self._client is not None and self._collection is not None:
            return

        try:
            import chromadb
        except ImportError:
            raise ImportError("缺少 chromadb。请运行: python -m pip install chromadb")

        try:
            # 新的 Chroma 客户端初始化方式
            self._client = chromadb.PersistentClient(path=self.persist_directory)
            
            # 获取或创建 collection
            self._collection = self._client.get_or_create_collection(name=self.collection_name)
            
            # 打印用于调试的持久化路径
            print(f"Chroma persist_directory = {self.persist_directory}")
            
        except Exception as e:
            raise RuntimeError(f"初始化 Chroma 客户端失败：{e}")
            # 打印用于调试的持久化路径
        print(f"Chroma persist_directory = {self.persist_directory}")

    def _init_embedder(self):
        if self._embedder is not None:
            return

        try:
            from zhipuai import ZhipuAI
        except ImportError:
            raise ImportError("缺少 zhipuai SDK。请运行: python -m pip install zhipuai")

        # 硬编码 API Key（按要求）
        api_key = "98ed0ed5a81f4a958432644de29cb547.LLhUp4oWijSoizYc"
        client = ZhipuAI(api_key=api_key)
        self._embedder = ("zhipuai", client)

    def _embed_batch(self, texts: List[str]) -> List[List[float]]:
        self._init_embedder()
        kind, embedder = self._embedder
        if kind != "zhipuai":
            raise RuntimeError("嵌入器未正确初始化")

        model_name = getattr(self, "_embed_model", "embedding-2")
        try:
            resp = embedder.embeddings.create(model=model_name, input=texts)
        except Exception as e:
            raise RuntimeError(f"调用 ZhipuAI 生成嵌入失败: {e}")

        embeddings: List[List[float]] = []

        # 兼容 dict 响应结构
        if isinstance(resp, dict) and resp.get("data"):
            for item in resp["data"]:
                emb = item.get("embedding")
                if emb is None:
                    raise RuntimeError("无法从 ZhipuAI 响应中提取 embedding 字段")
                embeddings.append(list(emb))
            return embeddings

        # 兼容对象属性风格
        data = getattr(resp, "data", None)
        if data:
            for item in data:
                emb = getattr(item, "embedding", None)
                if emb is None:
                    raise RuntimeError("无法从 ZhipuAI 响应中提取 embedding 字段")
                embeddings.append(list(emb))
            return embeddings

        raise RuntimeError("无法解析 ZhipuAI 嵌入响应格式")

    def add_documents(self, documents: List[str], metadatas: Optional[List[Dict[str, Any]]] = None,
                      ids: Optional[List[str]] = None, batch_size: int = 64) -> List[str]:
        if not documents:
            return []
        if metadatas is not None and len(metadatas) != len(documents):
            raise ValueError("metadatas 长度需与 documents 一致")
        if ids is not None and len(ids) != len(documents):
            raise ValueError("ids 长度需与 documents 一致")

        self._init_chroma()
        total = len(documents)
        ids_out = ids[:] if ids is not None else [str(uuid.uuid4()) for _ in range(total)]

        for start in range(0, total, batch_size):
            end = min(total, start + batch_size)
            batch_texts = documents[start:end]
            batch_ids = ids_out[start:end]
            batch_metadatas = (metadatas[start:end] if metadatas is not None
                               else [{} for _ in batch_texts])

            embeddings = self._embed_batch(batch_texts)

            # 不同版本 chromadb collection 写入方法兼容处理
            wrote = False
            try:
                # 新版使用 upsert
                self._collection.upsert(
                    ids=batch_ids,
                    documents=batch_texts,
                    metadatas=batch_metadatas,
                    embeddings=embeddings
                )
                wrote = True
            except Exception:
                try:
                    # 旧版可能使用 add
                    self._collection.add(
                        ids=batch_ids,
                        documents=batch_texts,
                        metadatas=batch_metadatas,
                        embeddings=embeddings
                    )
                    wrote = True
                except Exception as e:
                    raise RuntimeError(f"写入 Chroma collection 失败: {e}")

        # 尝试持久化（某些版本需要显式 persist）
        try:
            self._client.persist()
        except Exception:
            # 忽略 persist 失败（非致命）
            pass

        return ids_out

    def query(self, query_text: str, top_k: int = 5):
        if not query_text:
            return []
        self._init_chroma()
        q_emb = self._embed_batch([query_text])[0]

        # 不同版本可能返回格式不同，直接返回原始结果给调用者处理
        results = self._collection.query(query_embeddings=[q_emb], n_results=top_k,
                                         include=['metadatas', 'documents', 'distances'])
        return results

    def get_collection_info(self) -> Dict[str, Any]:
        self._init_chroma()
        try:
            data = self._collection.get()
            count = len(data.get('ids', []))
        except Exception:
            count = None
        return {
            "collection_name": self.collection_name,
            "persist_directory": self.persist_directory,
            "count": count
        }