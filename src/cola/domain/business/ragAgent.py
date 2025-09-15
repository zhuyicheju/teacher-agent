from search_knowledge import search_similar_knowledge
from zhipuai import ZhipuAI
from cola.infrastructure.externalServer.zhipuServer import zhipu_server
from typing import Optional


def rag_answer_stream(question: str, username: str = None, top_k: int = 5, thread_id: Optional[int] = None):
    """
    检索相关知识并结合LLM流式生成答案。
    username 用于在该用户的知识库中检索知识（若 None 则在全局库检索）。
    thread_id 可选；若提供，则会使用线程隔离的知识库标识（例如 username + thread_id 路径）。
    """
    print(f"[原始问题] {question}")
    level = zhipu_server.classify_question_level(question)
    print(f"[问题分级] 等级 {level}")

    if level == 1:
        # 1级：先改写，再检索，再流式总结
        rewritten = zhipu_server.rewrite_question(question)
        print(f"[改写后问题] {rewritten}")
        related_knowledge = search_similar_knowledge(rewritten, top_k=top_k, username=username, thread_id=thread_id)
        context = "\n".join([item["document"] for item in related_knowledge])
        yield from zhipu_server.summarize_answer_stream(question, context)

    elif level == 2:
        # 2级：分解为3个子问题，分别检索，最后流式总结
        sub_questions = zhipu_server.decompose_question(question)
        print(f"[分解为子问题] {sub_questions}")
        all_context = []
        for subq in sub_questions:
            related_knowledge = search_similar_knowledge(subq, top_k=top_k, username=username, thread_id=thread_id)
            context = "\n".join([item["document"] for item in related_knowledge])
            all_context.append(f"子问题：{subq}\n{context}")
        merged_context = "\n\n".join(all_context)
        yield from zhipu_server.summarize_answer_stream(question, merged_context)

    elif level == 3:
        # 3级问题处理流程
        problem_chain = [question]
        knowledge_system = []
        found_knowledges = []  # 新增：用于储存所有检索到的知识

        # 步骤1：分解为2个关键词，检索前置知识
        keywords1 = zhipu_server.extract_keywords(question, 2)
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
        subq1 = zhipu_server.generate_subquestion_first(pre_knowledge, question, client)
        print(f"[探索初步定义子问题] {subq1}")
        problem_chain.append(subq1)

        # 步骤3：子问题1分解为2关键词，检索知识，加入知识体系
        keywords2 = zhipu_server.extract_keywords(subq1, 2)
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
        subq2 = zhipu_server.generate_subquestion_second(merged_knowledge, question)
        print(f"[探索知识深度连接子问题] {subq2}")
        problem_chain.append(subq2)

        # 步骤5：子问题2分解为2关键词，检索知识，加入知识体系
        keywords3 = zhipu_server.extract_keywords(subq2, 2)
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
        final_context = (
            f"知识体系如下：\n{final_context}\n\n"
            f"问题链如下：\n{problem_chain_str}\n\n"
            f"请基于上述知识体系和问题链，系统性、深入地解答原始问题：{question}"
        )
        yield from zhipu_server.summarize_answer_stream(question, f"{final_context}\n\n问题链如下：\n{problem_chain_str}")