from vector_db import VectorDB

def search_similar_knowledge(question: str, top_k: int = 5):
    """
    根据问题question，检索知识库中最相关的top_k条知识。
    返回格式为列表，每项包含：文档内容、元数据、相似度分数。
    """
    db = VectorDB()
    results = db.query(question, top_k=top_k)
    if not results or not results.get('documents'):
        return []

    docs = results['documents'][0]
    metas = results['metadatas'][0]
    dists = results['distances'][0]

    # 组装结果
    return [
        {
            "document": doc,
            "metadata": meta,
            "distance": dist
        }
        for doc, meta, dist in zip(docs, metas, dists)
    ]

# 示例用法
if __name__ == "__main__":
    question = "什么是yolo"
    related_knowledge = search_similar_knowledge(question, top_k=5)
    for idx, item in enumerate(related_knowledge, 1):
        print(f"第{idx}条：")
        print("内容：", item["document"])
        print("元数据：", item["metadata"])
        print("相似度分数：", item["distance"])
        print("-" * 30)