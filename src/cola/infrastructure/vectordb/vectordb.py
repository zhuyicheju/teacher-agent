import os
import uuid
from typing import List, Optional, Dict, Any
import chromadb

from cola.infrastructure import config
from zhipuai import ZhipuAI

class VectorDB:
    """
    支持按 username 隔离的 Chroma collection / persist 目录。
    使用方式：VectorDB(username='alice') 会在 knowledge_base/chroma_alice 下持久化并创建 collection teacher_agent_alice。
    """
    def _sanitize(self, name: str) -> str:
        """把任意字符串清洗为文件/collection 安全的形式（只保留字母数字、下划线、短横线）"""
        if not name:
            return ''
        return ''.join(c if (c.isalnum() or c in ('_', '-')) else '_' for c in name)

    def __init__(self, persist_directory: Optional[str] = None, collection_name: Optional[str] = None, username: Optional[str] = None, thread_id: Optional[int] = None):
        # 支持两种用法：
        #  - 老调用：传入 username 字符串（可能包含 "__thread_"），此时会解析 thread_id（保持兼容）
        #  - 新调用：传入 username 和 thread_id 分别指定
        safe_username = None
        safe_thread = None
        if username and isinstance(username, str) and '__thread_' in username:
            # 兼容老式传参 username="user__thread_1"
            parts = username.split('__thread_')
            username = parts[0]
            try:
                thread_id = int(parts[1])
            except Exception:
                thread_id = thread_id  # 保持外部传入的为准
        if username:
            safe_username = self._sanitize(username)
        if thread_id is not None:
            safe_thread = str(thread_id)

        base = persist_directory or config.VECTOR_DIR
        if safe_username:
            # 在 per-user 目录下再创建 per-thread 子目录（若提供 thread_id）
            user_dir = os.path.join(base, safe_username)
            if safe_thread:
                self.persist_directory = os.path.join(user_dir, f"chroma_thread_{safe_thread}")
                self.collection_name = collection_name or f"teacher_agent_{safe_username}_thread_{safe_thread}"
            else:
                self.persist_directory = os.path.join(user_dir, "chroma_user")
                self.collection_name = collection_name or f"teacher_agent_{safe_username}"
        else:
            self.persist_directory = persist_directory or os.path.join(config.VECTOR_DIR, 'chroma_db')
            self.collection_name = collection_name or "teacher_agent"

        self._client = None
        self._collection = None
        self._embedder = None
        self._embed_model = "embedding-2"
        os.makedirs(self.persist_directory, exist_ok=True)

    def _init_chroma(self):
        if self._client is not None and self._collection is not None:
            return

        try:
            # 持久化客户端（不同 chromadb 版本可能不同）
            self._client = chromadb.PersistentClient(path=self.persist_directory)
            self._collection = self._client.get_or_create_collection(name=self.collection_name)
            print(f"Chroma persist_directory = {self.persist_directory}")
        except Exception as e:
            raise RuntimeError(f"初始化 Chroma 客户端失败：{e}")

    def _init_embedder(self):
        if self._embedder is not None:
            return

        api_key = config.API_KEY
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

        if isinstance(resp, dict) and resp.get("data"):
            for item in resp["data"]:
                emb = item.get("embedding")
                if emb is None:
                    raise RuntimeError("无法从 ZhipuAI 响应中提取 embedding 字段")
                embeddings.append(list(emb))
            return embeddings

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

            wrote = False
            try:
                self._collection.upsert(
                    ids=batch_ids,
                    documents=batch_texts,
                    metadatas=batch_metadatas,
                    embeddings=embeddings
                )
                wrote = True
            except Exception:
                try:
                    self._collection.add(
                        ids=batch_ids,
                        documents=batch_texts,
                        metadatas=batch_metadatas,
                        embeddings=embeddings
                    )
                    wrote = True
                except Exception as e:
                    raise RuntimeError(f"写入 Chroma collection 失败: {e}")

        try:
            self._client.persist()
        except Exception:
            pass

        return ids_out

    def query(self, query_text: str, top_k: int = 5):
        if not query_text:
            return []
        self._init_chroma()
        q_emb = self._embed_batch([query_text])[0]
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

    def delete_documents(self, ids: List[str]):
        """
        删除指定 ids（向量/文档 id），仅在当前 persist_directory/collection 上操作。
        """
        if not ids:
            return
        self._init_chroma()
        try:
            # 主流 chroma 接口：collection.delete(ids=[...])
            self._collection.delete(ids=ids)
        except Exception as e:
            # 若接口不同，尝试备选方案并抛出可读错误
            try:
                # 有些版本使用 where 参数或 delete({'ids': ids})
                self._collection.delete({'ids': ids})
            except Exception as e2:
                raise RuntimeError(f"删除 Chroma 中 ids 失败: {e} / {e2}")
        # 尝试持久化
        try:
            self._client.persist()
        except Exception:
            pass