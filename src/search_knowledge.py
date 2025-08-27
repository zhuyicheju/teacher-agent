from vector_db import VectorDB

def search_similar_knowledge(question: str, top_k: int = 5, username: str = None):
    """
    根据问题 question，在指定 username 的向量库中检索相似知识（若 username 为 None 则使用全局库）。
    返回列表：{document, metadata, distance}
    """
    db = VectorDB(username=username)
    results = db.query(question, top_k=top_k)
    if not results or not results.get('documents'):
        return []

    docs = results['documents'][0]
    metas = results['metadatas'][0]
    dists = results['distances'][0]

    return [
        {
            "document": doc,
            "metadata": meta,
            "distance": dist
        }
        for doc, meta, dist in zip(docs, metas, dists)
    ]

if __name__ == "__main__":
    question = "什么是yolo"
    related_knowledge = search_similar_knowledge(question, top_k=5, username=None)
    for idx, item in enumerate(related_knowledge, 1):
        print(f"第{idx}条：")
        print("内容：", item["document"])
        print("元数据：", item["metadata"])
        print("相似度分数：", item["distance"])
        print("-" * 30)