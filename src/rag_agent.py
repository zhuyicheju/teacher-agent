from search_knowledge import search_similar_knowledge
from zhipuai import ZhipuAI

def rag_answer(question: str, top_k: int = 5) -> str:
    """
    检索相关知识并结合LLM生成答案
    """
    # 1. 检索相关知识
    related_knowledge = search_similar_knowledge(question, top_k=top_k)
    # 拼接知识内容
    context = "\n".join([item["document"] for item in related_knowledge])
    print("检索到的相关知识：", context)

    # 2. 构造prompt
    prompt = f"已知知识如下：\n{context}\n\n请根据上述知识回答用户问题：{question}"

    # 3. 调用大模型生成答案
    client = ZhipuAI(api_key="98ed0ed5a81f4a958432644de29cb547.LLhUp4oWijSoizYc")
    response = client.chat.completions.create(
        model="glm-4-0520",
        messages=[
            {"role": "user", "content": prompt},
        ]
    )
    # 兼容对象和dict两种返回
    if hasattr(response, "choices"):
        return response.choices[0].message.content
    elif isinstance(response, dict):
        return response.get("choices", [{}])[0].get("message", {}).get("content", "")
    else:
        return "模型未返回有效答案"

# 示例用法
if __name__ == "__main__":
    question = "什么是yolo"
    answer = rag_answer(question)
    print("RAG生成的答案：", answer)