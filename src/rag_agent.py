from search_knowledge import search_similar_knowledge
from zhipuai import ZhipuAI

def rag_answer_stream(question: str, username: str = None, top_k: int = 5):
    """
    检索相关知识并结合LLM流式生成答案。
    username 用于在该用户的知识库中检索知识（若 None 则在全局库检索）。
    """
    related_knowledge = search_similar_knowledge(question, top_k=top_k, username=username)
    context = "\n".join([item["document"] for item in related_knowledge])
    print("检索到的相关知识（username={}）：\n{}".format(username, context))
    prompt = f"已知知识如下：\n{context}\n\n请根据上述知识回答用户问题：{question}"

    client = ZhipuAI(api_key="98ed0ed5a81f4a958432644de29cb547.LLhUp4oWijSoizYc")
    response = client.chat.completions.create(
        model="glm-4-0520",
        messages=[
            {"role": "user", "content": prompt},
        ],
        stream=True
    )
    try:
        for chunk in response:
            if hasattr(chunk, 'choices') and chunk.choices:
                delta = chunk.choices[0].delta
                if hasattr(delta, 'content') and delta.content:
                    yield delta.content
    except Exception as e:
        yield f"[ERROR]{str(e)}"