from zhipuai import ZhipuAI
import datetime

def extract_keywords(question: str, client) -> list:
    """
    用大模型提取问题的关键词，返回指定数量。
    """
    prompt = (
        f"""
        <目标>
        您是一名专家级的信息整合专家，专注于通过多源信息检索、多跳推理和对比分析，解决需要隐性事实挖掘的复杂问题。能够根据用户问题，采用链式推理生成1-4个精准检索关键词，用于高效获取分散但关键的信息。
        </目标>

        <核心流程>
        1. **需求解析**：
        * 判断问题类型：多跳推理需串联多个信息片段，对比类需提取异同维度，总结类需识别核心要素。
        * 明确信息缺口：用户未直接陈述但必须推导的隐性事实（如时间线、因果关系、领域术语关联）。
        2. **推理链构建**：
        * 将问题分解为逻辑递进的子问题，确保每一步仅依赖前序检索结果。
        * 对对比类问题，生成可比性框架（如"特性A vs 特性B"）。
        3. **关键词生成**：
        * 每个关键词需覆盖一个信息缺口，避免冗余（如["量子计算原理", "传统计算机局限"]而非"量子计算机与传统计算机对比"）。
        </核心流程>

        <任务要求>
        - 输出格式：["keyword1", "keyword2"]（严格列表形式）
        - 除了一个列表，禁止返回其他任何内容！
        - 禁用词：无需包含"研究""分析"等动词。
        </任务要求>

        <用户输入>
        原始问题：{question}
        当前日期：{datetime.datetime.now()}
        </用户输入>
        """
    )
    resp = client.chat.completions.create(
        model="glm-4-0520",
        messages=[{"role": "user", "content": prompt}]
    )
    content = resp.choices[0].message.content.strip()
    import ast
    keywords = []
    try:
        keywords = ast.literal_eval(content)
        if not isinstance(keywords, list):
            keywords = []
    except Exception:
        keywords = [k.strip("[]\"' ") for k in content.replace("，", ",").split(",") if k.strip()]
    return keywords

client = ZhipuAI(api_key="98ed0ed5a81f4a958432644de29cb547.LLhUp4oWijSoizYc")
question = "请帮我设计一个计算机学习框架"
answer = extract_keywords(question=question, client=client)
print(answer)