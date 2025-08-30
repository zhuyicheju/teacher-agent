from typing import List, Optional
import os
import sqlite3
from flask import Blueprint, request, jsonify, session, current_app
from pathlib import Path
import shutil
import traceback
from vector_db import VectorDB

# 复用已有实现
from knowledge_processor import list_user_document_titles

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(base_dir, 'data', 'users.db')

def get_user_titles(username: str, thread_id: Optional[int] = None, limit: int = 100) -> List[str]:
    """
    返回指定用户名下已存知识文档的标题列表（仅标题字符串）。
    thread_id 可选：若提供则仅返回该会话下的文档（实现会话级隔离）。
    limit 可控返回数量。
    """
    items = list_user_document_titles(username, limit=limit, thread_id=thread_id)
    return [it.get('title') or it.get('filename') or '' for it in items]

def delete_thread(thread_id):
    if not session.get('user'):
        return jsonify({'error': '未登录'}), 401
    username = session.get('user')

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # 校验线程归属
    cur.execute('SELECT 1 FROM threads WHERE id = ? AND username = ?', (thread_id, username))
    if not cur.fetchone():
        conn.close()
        return jsonify({'error': '未找到线程或无权限'}), 404

    try:
        # 获取该线程下的所有文档 id
        cur.execute('SELECT id FROM documents WHERE thread_id = ? AND username = ?', (thread_id, username))
        docs = [r[0] for r in cur.fetchall()]

        # 收集所有 vector_id
        vector_ids = []
        if docs:
            cur.execute('SELECT vector_id FROM document_segments WHERE document_id IN ({seq})'.format(
                seq=','.join(['?']*len(docs))
            ), docs)
            vector_ids = [r[0] for r in cur.fetchall() if r and r[0]]

        # 删除向量（在对应命名空间/collection）
        try:
            vdb = VectorDB(username=username, thread_id=thread_id)
            if vector_ids:
                vdb.delete_documents(vector_ids)
        except Exception as e:
            # 记录但不阻塞后续删除
            print("删除向量失败：", e, traceback.format_exc())

        # 尝试移除 Chroma 持久化目录（彻底清除会话知识库数据）
        try:
            vdb = VectorDB(username=username, thread_id=thread_id)
            persist_dir = getattr(vdb, 'persist_directory', None)
            if persist_dir and os.path.isdir(persist_dir):
                shutil.rmtree(persist_dir, ignore_errors=True)
        except Exception as e:
            print("移除 persist_directory 失败：", e)

        # 删除 raw_documents 目录下该线程的源文件
        try:
            raw_dir = os.path.abspath(os.path.join(base_dir, 'data', 'raw_documents', username, f"thread_{thread_id}"))
            if os.path.isdir(raw_dir):
                shutil.rmtree(raw_dir, ignore_errors=True)
        except Exception as e:
            print("移除 raw_documents 失败：", e)

        # 在事务中删除 DB 中的 messages、document_segments、documents、threads
        try:
            cur.execute('DELETE FROM messages WHERE thread_id = ? AND username = ?', (thread_id, username))
            if docs:
                cur.execute('DELETE FROM document_segments WHERE document_id IN ({seq})'.format(
                    seq=','.join(['?']*len(docs))
                ), docs)
                cur.execute('DELETE FROM documents WHERE id IN ({seq}) AND username = ?'.format(
                    seq=','.join(['?']*len(docs))
                ), docs + [username])
            cur.execute('DELETE FROM threads WHERE id = ? AND username = ?', (thread_id, username))
            conn.commit()
        except Exception as e:
            conn.rollback()
            print("删除数据库记录失败：", e, traceback.format_exc())
            conn.close()
            return jsonify({'error': f'删除数据库记录失败: {e}'}), 500

    except Exception as e:
        conn.rollback()
        conn.close()
        print("删除线程过程中出错：", e, traceback.format_exc())
        return jsonify({'error': str(e)}), 500

    conn.close()
    return jsonify({'success': True})

def delete_thread_action(thread_id: int, username: str):
    """
    以显式 username 删除线程及其所有相关数据（向量、持久化目录、raw 文件、DB 记录）。
    返回 (success: bool, message: str)
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # 校验线程归属
    cur.execute('SELECT 1 FROM threads WHERE id = ? AND username = ?', (thread_id, username))
    if not cur.fetchone():
        conn.close()
        return False, "未找到线程或无权限"

    try:
        # 获取该线程下的所有文档 id
        cur.execute('SELECT id FROM documents WHERE thread_id = ? AND username = ?', (thread_id, username))
        docs = [r[0] for r in cur.fetchall()]

        # 收集所有 vector_id
        vector_ids = []
        if docs:
            cur.execute('SELECT vector_id FROM document_segments WHERE document_id IN ({seq})'.format(
                seq=','.join(['?']*len(docs))
            ), docs)
            vector_ids = [r[0] for r in cur.fetchall() if r and r[0]]

        # 删除向量（在对应命名空间/collection）
        try:
            vdb = VectorDB(username=username, thread_id=thread_id)
            if vector_ids:
                vdb.delete_documents(vector_ids)
        except Exception as e:
            print("删除向量失败：", e, traceback.format_exc())

        # 尝试移除 Chroma 持久化目录（彻底清除会话知识库数据）
        try:
            vdb = VectorDB(username=username, thread_id=thread_id)
            persist_dir = getattr(vdb, 'persist_directory', None)
            if persist_dir and os.path.isdir(persist_dir):
                shutil.rmtree(persist_dir, ignore_errors=True)
        except Exception as e:
            print("移除 persist_directory 失败：", e)

        # 删除 raw_documents 目录下该线程的源文件
        try:
            raw_dir = os.path.abspath(os.path.join(base_dir, 'data', 'raw_documents', username, f"thread_{thread_id}"))
            if os.path.isdir(raw_dir):
                shutil.rmtree(raw_dir, ignore_errors=True)
        except Exception as e:
            print("移除 raw_documents 失败：", e)

        # 在事务中删除 DB 中的 messages、document_segments、documents、threads
        try:
            cur.execute('DELETE FROM messages WHERE thread_id = ? AND username = ?', (thread_id, username))
            if docs:
                cur.execute('DELETE FROM document_segments WHERE document_id IN ({seq})'.format(
                    seq=','.join(['?']*len(docs))
                ), docs)
                cur.execute('DELETE FROM documents WHERE id IN ({seq}) AND username = ?'.format(
                    seq=','.join(['?']*len(docs))
                ), docs + [username])
            cur.execute('DELETE FROM threads WHERE id = ? AND username = ?', (thread_id, username))
            conn.commit()
        except Exception as e:
            conn.rollback()
            conn.close()
            return False, f'删除数据库记录失败: {e}'

    except Exception as e:
        conn.rollback()
        conn.close()
        return False, str(e)

    conn.close()
    return True, "删除成功"

# 简单命令行测试（仅在直接运行此文件时执行）
if __name__ == "__main__":
    import sys
    from flask import Flask
    from collections import defaultdict
    
    # 创建一个简单的Flask应用上下文来模拟会话
    app = Flask(__name__)
    app.secret_key = 'cli-secret-key'
    
    if len(sys.argv) < 2:
        print("用法:")
        print("  查看文档: python script.py list <username> [thread_id]")
        print("  删除线程: python script.py delete <username> <thread_id>")
        print("  查看帮助: python script.py help")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == 'list':
        if len(sys.argv) < 3:
            print("用法: python script.py list <username> [thread_id]")
            sys.exit(1)
        
        username = sys.argv[2]
        thread_id = None
        
        if len(sys.argv) >= 4:
            try:
                thread_id = int(sys.argv[3])
            except ValueError:
                print("错误: thread_id 必须是整数")
                sys.exit(1)
        
        # 这里需要导入或实现 list_user_document_titles 函数
        try:
            from knowledge_processor import list_user_document_titles
            
            if thread_id is not None:
                # 查看指定线程的文档
                items = list_user_document_titles(username, thread_id=thread_id)
                print(f"\n=== 线程 {thread_id} 的文档 ===")
                for item in items:
                    title = item.get('title') or item.get('filename') or '无标题'
                    print(f"  {title}")
            else:
                # 查看所有线程的文档（按线程分组）
                items = list_user_document_titles(username, limit=100)
                thread_docs = defaultdict(list)
                for item in items:
                    tid = item.get('thread_id', 0)
                    title = item.get('title') or item.get('filename') or '无标题'
                    thread_docs[tid].append(title)
                
                for tid, titles in thread_docs.items():
                    print(f"\n=== 线程 {tid} ===")
                    for title in titles:
                        print(f"  {title}")
        
        except ImportError:
            print("错误: 无法导入 list_user_document_titles 函数")
        except Exception as e:
            print(f"错误: {e}")
    
    elif command == 'delete':
        if len(sys.argv) < 4:
            print("用法: python script.py delete <username> <thread_id>")
            sys.exit(1)

        username = sys.argv[2]
        thread_arg = sys.argv[3]
        # 支持传入 'thread_22' 或 '22'
        try:
            if isinstance(thread_arg, str) and thread_arg.startswith('thread_'):
                thread_id = int(thread_arg.split('thread_', 1)[1])
            else:
                thread_id = int(thread_arg)
        except Exception:
            print("错误: thread_id 必须是整数或形如 'thread_<id>'")
            sys.exit(1)

        # 确认操作
        confirm = input(f"⚠️  确认要删除用户 '{username}' 的线程 {thread_id} 吗？此操作不可恢复！(y/N): ")
        if confirm.lower() != 'y':
            print("操作已取消")
            sys.exit(0)

        # 直接以 username 调用删除动作（不依赖 Flask session）
        ok, msg = delete_thread_action(thread_id, username)
        if ok:
            print(f"✅ 成功删除线程 {thread_id} 及其所有相关内容")
        else:
            print(f"❌ 删除失败: {msg}")
    
    elif command == 'help':
        print("线程和文档管理工具")
        print("命令:")
        print("  list <username> [thread_id] - 查看用户的文档列表")
        print("  delete <username> <thread_id> - 删除指定用户的线程")
        print("  help - 显示帮助信息")
        print("\n示例:")
        print("  python script.py list alice - 查看用户alice的所有文档")
        print("  python script.py list alice 123 - 查看用户alice线程123的文档")
        print("  python script.py delete alice 123 - 删除用户alice的线程123")
    
    else:
        print(f"未知命令: {command}")
        print("使用 'python script.py help' 查看可用命令")
        sys.exit(1)