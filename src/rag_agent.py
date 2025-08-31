from search_knowledge import search_similar_knowledge
from zhipuai import ZhipuAI
import datetime
from typing import Optional
import re  # 新增：用于规范化换行

def classify_question_level(question: str, client) -> int:
    """
    使用大模型对问题进行分级，返回等级1/2/3。
    """
    prompt = (
        f"""
        <目标>
        您是一名专业的问题分级专家，专注于将问题精准分类为三个难度等级（L1-L3），特别擅长识别需要多维度分析的复杂问题。
        </目标>

        <核心流程>
        1. **问题解构与分析**
        - 1.1 要素提取
            * 核心实体识别（技术术语/业务概念）
            * 关系动词标注：
            ["解释","对比","诊断","优化","决策","评估","解决"]
            * 约束条件捕获（时间/成本/性能/质量等）

        - 1.2 需求类型诊断矩阵
            | 需求特征                | 输出形式       | 等级线索              |
            |-------------------------|---------------|-----------------------|
            | 基础定义与描述          | 术语表        | 有标准答案（L1）      |
            | 比较分析与判断          | 对比表        | 需多维度分析（L2）    |
            | 复杂问题解决            | 解决方案      | 需创新思维（L3）      |

        2. **智能分级引擎**
        - 2.1 三级决策标准
            | Level | 判定标准                          | 验证问题                  |
            |-------|-----------------------------------|---------------------------|
            | L1    | 答案存在于标准资料库              | "是否有明确的标准答案？"  |
            | L2    | 需比较分析或简单推理              | "是否需要对比多个因素？"  |
            | L3    | 需满足以下任意一条：              |                           |
            |       | 1. 涉及≥2个相互制约的决策维度     | "是否有冲突的目标？"      |
            |       | 2. 需要创造性解决问题             | "是否无现成解决方案？"    |
            |       | 3. 涉及风险评估或权衡取舍         | "是否需要平衡利弊？"      |

        - 2.2 分级精炼检测
            * L3特征识别：
            - 检查是否包含复杂动词（优化/决策/评估）
            - 识别多重约束条件（成本与性能的平衡等）
            - 捕捉问题复杂度关键词（最佳实践/策略/方案）
        </核心流程>

        <任务要求>
        1. 严格根据三级标准输出1-3的整数等级
        2. 对疑似L3的问题重点检测多重约束和创新要求
        3. 禁止任何解释性文本，仅返回数字

        <用户输入>
        - 当前时间：{datetime.datetime.now()}
        - 原始问题：{question}
        </用户输入>

        请直接输出等级数字：
        """
    )
    resp = client.chat.completions.create(
        model="glm-4-0520",
        messages=[{"role": "user", "content": prompt}]
    )
    content = resp.choices[0].message.content.strip()
    try:
        level = int(content[0])
        if level in (1, 2, 3):
            return level
    except Exception:
        pass
    return 1  # 默认1级

def rewrite_question(question: str, client) -> str:
    """
    用大模型将问题改写为更明确的问题。
    """
    prompt = (
        f""""
        你是一位专业的问题重构专家。请对用户输入的问题进行精准改写，使其成为更明确、更具可操作性的问题。

        【任务要求】
        1. 改写原则：
        - 具体化：将抽象概念转化为具体可操作的表述
        - 直接化：尽可能准确找出用户需求，以简短而精准的表达进行改写
        - 明确目标：清晰定义期望的输出或解决方案
        - 可衡量：确保问题有明确的成功标准

        2. 输出标准：
        - 改写后的问题必须保持原问题的核心意图
        - 避免引入新的假设或改变问题本质
        - 确保问题具备可回答性

        【重要约束】
        - 如果输入问题已经明确具体，请保持原问题不变
        - 不得添加与原始问题无关的新内容
        - 每个改写必须附带修改说明
        - 除了改写后的问题，禁止输出其他任何内容！

        用户输入的问题：{question},请直接输出改写后的问题：
        """
    )
    resp = client.chat.completions.create(
        model="glm-4-0520",
        messages=[{"role": "user", "content": prompt}]
    )
    return resp.choices[0].message.content.strip()

def decompose_question(question: str, client) -> list:
    """
    用大模型将问题分解为3个子问题。
    """
    prompt = (
        f"""
        <目标>
        您是一名专家级决策架构师，专注于将开放性问题转化为可操作的决策流程。能够显性化推理路径，生成带分支条件（是/否）的检索步骤，确保每个关键词对应决策树的一个节点。
        </目标>

        <核心流程>
        1. **决策点识别**：
        * 标注问题中的判断条件（如"如果...则应..."、"取决于..."）。
        * 将模糊需求转化为二元分支（例："选择X还是Y" → "X的适用条件"+"Y的适用条件"）。
        2. **路径结构化**：
        * 为每个决策点生成互斥检索词，确保覆盖所有可能路径。
        * 对依赖时间/上下文的问题，添加筛选词（如"2023年后"、"开源方案"）。
        3. **验证闭环**：
        * 最终关键词必须能验证前序决策合理性（如步骤3检索结果应能反推步骤1的选择）。
        </核心流程>

        <任务要求>
        - 输出格式：["decision1_conditionA", "decision1_conditionB", "validation_query"]
        - 必须包含条件分支词（如"优点"/"缺点"、"支持"/"反对"）。
        - 示例：
        输入："小微企业该用MySQL还是MongoDB？"
        输出：["MySQL小微企业使用场景", "MongoDB小微企业使用场景", "NoSQL与SQL事务需求对比"]
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
    subs = []
    try:
        subs = ast.literal_eval(content)
        if not isinstance(subs, list):
            subs = []
    except Exception:
        subs = [s.strip("[]\"' ") for s in content.replace("，", ",").split(",") if s.strip()]
    return subs[:3]

def generate_title_sync(question: str, username: str = None, client: ZhipuAI = None, thread_id: Optional[int] = None, top_k: int = 1) -> str:
    """
    同步生成会话标题（非流式），不使用 summarize_answer_stream。
    返回清洗后的单行标题字符串。
    """
    if client is None:
        client = ZhipuAI(api_key="98ed0ed5a81f4a958432644de29cb547.LLhUp4oWijSoizYc")
    prompt = f"请基于用户的问题生成一句简短且明确的会话标题（尽量不超过20个字）：{question}"
    try:
        resp = client.chat.completions.create(
            model="glm-4-0520",
            messages=[{"role": "user", "content": prompt}],
            stream=False
        )
        content = resp.choices[0].message.content.strip() if getattr(resp, 'choices', None) else str(resp)
    except Exception as e:
        # 返回空字符串以在调用端处理错误
        print("generate_title_sync error:", e)
        content = ""
    # 简单清洗：去多余换行/空白
    title = re.sub(r"\s+", " ", content).strip()
    if len(title) > 120:
        title = title[:120].rstrip() + "..."
    return title

def summarize_answer_stream(question: str, context: str, client):
    """
    用大模型根据知识片段流式总结最终答案。
    """
    prompt = (
        f"已知知识如下：\n{context}\n\n请根据上述知识，简明、准确地回答用户问题：{question}。"
    )
    response = client.chat.completions.create(
        model="glm-4-0520",
        messages=[{"role": "user", "content": prompt}],
        stream=True
    )
    try:
        for chunk in response:
            if hasattr(chunk, 'choices') and chunk.choices:
                delta = chunk.choices[0].delta
                content = getattr(delta, 'content', '') or ''
                if content:
                    # 同步打印到服务器终端，便于实时查看（不改变返回内容）
                    print(content, end='', flush=True)
                    yield content
    except Exception as e:
        yield f"[ERROR]{str(e)}"

def extract_keywords(question: str, client, num_keywords: int = 2) -> list:
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
    return keywords[:num_keywords]

def generate_subquestion_first(context: str, question: str, client) -> str:
    """
    用大模型根据上下文和原问题生成子问题。
    """
    prompt = (
        f"""
        <角色>
        你是一位信息架构师，擅长对复杂问题进行解构和定义。你的任务是为用户输入的原始问题生成一个精准的、用于获取基础性定义和共识性的子问题。
        </角色>

        <核心任务>
        针对用户输入的原始问题，生成一个用于“搜索定义与基础知识”的子问题。这个子问题应能引导搜索行为，从而获取到理解该问题所必需的核心概念、权威数据、公认事实及明确的问题边界。
        </核心任务>

        <思考框架>
        在生成子问题时，请遵循以下框架：
        1.  **概念界定 (Conceptualization):** 问题中哪些关键术语、概念或实体需要清晰、无歧义的定义？
        2.  **现状描绘 (State Description):** 关于这个问题，目前有哪些公认的、基于事实的数据、统计信息或背景情况？
        3.  **范围划定 (Scoping):** 问题的直接影响范围和核心相关领域是什么？需要排除哪些次要或无关的信息？
        </思考框架>

        <输出要求>
        - 生成的子问题必须是一个可以直接用于知识库或搜索引擎查询的、具体的问题句式。
        - 输出格式必须严格遵循：["你的子问题内容"]
        - 子问题应中立、客观，专注于获取事实性、定义性的知识，避免涉及深度分析、因果推断或隐藏关系。
        </输出要求>

        <用户输入>
        - 原始问题：{question}
        - 当前已检索到的知识（用于参考）：{context}
        </用户输入>

        请基于上述“当前已检索到的知识”和原始问题，生成子问题：
        """
    )
    resp = client.chat.completions.create(
        model="glm-4-0520",
        messages=[{"role": "user", "content": prompt}]
    )
    content = resp.choices[0].message.content.strip()
    import ast
    try:
        result = ast.literal_eval(content)
        if isinstance(result, list) and result:
            return result[0]
    except Exception:
        pass
    return content

def generate_subquestion_second(context: str, question: str, client) -> str:
    """
    用大模型根据上下文和原问题生成子问题，purpose为子问题目标描述。
    """
    prompt = (
        f"""
        <角色>
        你是一位战略分析师，擅长洞察信息背后的深层联系和矛盾。你的任务是基于第一步获得的基础知识，生成一个用于挖掘潜在机制、冲突和未明说关系的子问题。
        </角色>

        <核心任务>
        基于用户提供的**原始问题**和**第一步搜索到的定义与知识**，生成一个用于“探索深度关系与隐藏模式”的子问题。这个子问题应能引导搜索去发现信息之间的因果链、权衡取舍（Trade-offs）、利益冲突以及未被广泛讨论的潜在因素。
        </核心任务>

        <思考框架>
        在生成子问题时，请重点考虑：
        1.  **矛盾与分歧 (Contradictions):** 第一步收集的信息中，是否存在不同来源的数据、观点或结论有冲突或不一致的地方？其背后可能的原因是什么？
        2.  **因果机制 (Causality):**  beyond表面的相关性，哪些是驱动该问题的深层原因或影响因素？其中哪些是显而易见的，哪些是隐藏的？
        3.  **利益相关方分析 (Stakeholder Analysis):** 哪些组织、群体或个人的未明说的利益、动机或约束条件在影响这个问题的表现或发展？
        4.  **跨领域洞察 (Cross-domain Insight):** 其他领域（如生物学、经济学、社会学）中的哪些模型或理论可以用来类比和解释当前问题中的复杂关系？
        </思考框架>

        <输出要求>
        - 生成的子问题应是一个探索性、分析性的问题，旨在挖掘“为什么”和“怎么样”，而不仅仅是“是什么”。
        - 输出格式必须严格遵循：["你的子问题内容"]
        - 子问题应明确体现出对第一步知识的承接与发展，并直接指向需要深度挖掘的非显性信息。
        </输出要求>

        <用户输入>
        - 原始问题：{question}
        - 第一步/当前已检索到的知识（用于参考）：{context}
        </用户输入>

        请基于上述“当前已检索到的知识”和原始问题，生成用于挖掘深层关系的子问题：
        """
    )
    resp = client.chat.completions.create(
        model="glm-4-0520",
        messages=[{"role": "user", "content": prompt}]
    )
    content = resp.choices[0].message.content.strip()
    import ast
    try:
        result = ast.literal_eval(content)
        if isinstance(result, list) and result:
            return result[0]
    except Exception:
        pass
    return content

def rag_answer_stream(question: str, username: str = None, top_k: int = 5, thread_id: Optional[int] = None):
    """
    检索相关知识并结合LLM流式生成答案。
    username 用于在该用户的知识库中检索知识（若 None 则在全局库检索）。
    thread_id 可选；若提供，则会使用线程隔离的知识库标识（例如 username + thread_id 路径）。
    """
    client = ZhipuAI(api_key="98ed0ed5a81f4a958432644de29cb547.LLhUp4oWijSoizYc")
    print(f"[原始问题] {question}")
    level = classify_question_level(question, client)
    print(f"[问题分级] 等级 {level}")

    if level == 1:
        # 1级：先改写，再检索，再流式总结
        rewritten = rewrite_question(question, client)
        print(f"[改写后问题] {rewritten}")
        related_knowledge = search_similar_knowledge(rewritten, top_k=top_k, username=username, thread_id=thread_id)
        context = "\n".join([item["document"] for item in related_knowledge])
        yield from summarize_answer_stream(question, context, client)

    elif level == 2:
        # 2级：分解为3个子问题，分别检索，最后流式总结
        sub_questions = decompose_question(question, client)
        print(f"[分解为子问题] {sub_questions}")
        all_context = []
        for subq in sub_questions:
            related_knowledge = search_similar_knowledge(subq, top_k=top_k, username=username, thread_id=thread_id)
            context = "\n".join([item["document"] for item in related_knowledge])
            all_context.append(f"子问题：{subq}\n{context}")
        merged_context = "\n\n".join(all_context)
        yield from summarize_answer_stream(question, merged_context, client)

    elif level == 3:
        # 3级问题处理流程
        problem_chain = [question]
        knowledge_system = []
        found_knowledges = []  # 新增：用于储存所有检索到的知识

        # 步骤1：分解为2个关键词，检索前置知识
        keywords1 = extract_keywords(question, client, 2)
        print(f"[分解为关键词1] {keywords1}")
        pre_contexts = []
        for kw in keywords1:
            rel = search_similar_knowledge(kw, top_k=top_k, username=username, thread_id=thread_id)
            ctx = "\n".join([item["document"] for item in rel])
            pre_contexts.append(f"关键词：{kw}\n{ctx}")
            found_knowledges.extend(rel)  # 保存检索到的知识
        pre_knowledge = "\n\n".join(pre_contexts)
        knowledge_system.append(pre_knowledge)

        # 步骤2：生成探索初步定义的子问题
        subq1 = generate_subquestion_first(pre_knowledge, question, client)
        print(f"[探索初步定义子问题] {subq1}")
        problem_chain.append(subq1)

        # 步骤3：子问题1分解为2关键词，检索知识，加入知识体系
        keywords2 = extract_keywords(subq1, client, 2)
        print(f"[子问题1分解为关键词2] {keywords2}")
        sub1_contexts = []
        for kw in keywords2:
            rel = search_similar_knowledge(kw, top_k=top_k, username=username, thread_id=thread_id)
            ctx = "\n".join([item["document"] for item in rel])
            sub1_contexts.append(f"关键词：{kw}\n{ctx}")
            found_knowledges.extend(rel)
        sub1_knowledge = "\n\n".join(sub1_contexts)
        knowledge_system.append(sub1_knowledge)

        # 步骤4：生成探索知识深度连接的子问题
        merged_knowledge = "\n\n".join(knowledge_system)
        subq2 = generate_subquestion_second(merged_knowledge, question, client)
        print(f"[探索知识深度连接子问题] {subq2}")
        problem_chain.append(subq2)

        # 步骤5：子问题2分解为2关键词，检索知识，加入知识体系
        keywords3 = extract_keywords(subq2, client, 2)
        print(f"[子问题2分解为关键词3] {keywords3}")
        sub2_contexts = []
        for kw in keywords3:
            rel = search_similar_knowledge(kw, top_k=top_k, username=username, thread_id=thread_id)
            ctx = "\n".join([item["document"] for item in rel])
            sub2_contexts.append(f"关键词：{kw}\n{ctx}")
            found_knowledges.extend(rel)
        sub2_knowledge = "\n\n".join(sub2_contexts)
        knowledge_system.append(sub2_knowledge)

        # 步骤6：汇总知识体系与问题链，交给大模型流式总结
        final_context = "\n\n".join(knowledge_system)
        problem_chain_str = "\n".join([f"{i+1}. {q}" for i, q in enumerate(problem_chain)])
        final_prompt = (
            f"知识体系如下：\n{final_context}\n\n"
            f"问题链如下：\n{problem_chain_str}\n\n"
            f"请基于上述知识体系和问题链，系统性、深入地解答原始问题：{question}"
        )
        response = client.chat.completions.create(
            model="glm-4-0520",
            messages=[{"role": "user", "content": final_prompt}],
            stream=True
        )
        try:
            for chunk in response:
                if hasattr(chunk, 'choices') and chunk.choices:
                    delta = chunk.choices[0].delta
                    content = getattr(delta, 'content', '') or ''
                    if content:
                        # 打印到终端以便调试/监控
                        print(content, end='', flush=True)
                        yield content
        except Exception as e:
            yield f"[ERROR]{str(e)}"