import os
import sqlite3
from flask import Blueprint, request, jsonify, session, current_app
from pathlib import Path

# 使用与项目一致的 DB_PATH 计算方式（不直接依赖 circular import）
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(base_dir, 'data', 'users.db')

delete_app = Blueprint('delete', __name__)

def document_belongs_to_user(doc_id: int, username: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT filename FROM documents WHERE id = ? AND username = ?', (doc_id, username))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

@delete_app.route('/threads/<int:thread_id>', methods=['DELETE'])
def delete_thread(thread_id):
    if not session.get('user'):
        return jsonify({'error': '未登录'}), 401
    username = session.get('user')
    # 先校验归属（简单查询 threads 表）
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT 1 FROM threads WHERE id = ? AND username = ?', (thread_id, username))
    if not cur.fetchone():
        conn.close()
        return jsonify({'error': '未找到线程或无权限'}), 404
    try:
        # 删除该线程的消息与线程记录（按 username 双重保障）
        cur.execute('DELETE FROM messages WHERE thread_id = ? AND username = ?', (thread_id, username))
        cur.execute('DELETE FROM threads WHERE id = ? AND username = ?', (thread_id, username))
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({'error': str(e)}), 500
    conn.close()
    return jsonify({'success': True})

@delete_app.route('/my_documents/<int:doc_id>', methods=['DELETE'])
def delete_document(doc_id):
    if not session.get('user'):
        return jsonify({'error': '未登录'}), 401
    username = session.get('user')
    # 验证文档归属并取得文件名（若有）
    filename = document_belongs_to_user(doc_id, username)
    if filename is None:
        return jsonify({'error': '未找到该文档或无权限'}), 404

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    try:
        # 先删除分段记录，再删除文档记录
        cur.execute('DELETE FROM document_segments WHERE document_id = ?', (doc_id,))
        cur.execute('DELETE FROM documents WHERE id = ? AND username = ?', (doc_id, username))
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({'error': str(e)}), 500
    conn.close()

    # 尝试从磁盘删除对应文件（如果能定位到）
    try:
        # 如果 filename 是绝对路径，直接尝试删除；否则尝试常见上传目录
        possible_paths = []
        if os.path.isabs(filename):
            possible_paths.append(filename)
        else:
            possible_paths.append(os.path.join(base_dir, 'uploads', filename))
            possible_paths.append(os.path.join(base_dir, 'data', 'uploads', filename))
            possible_paths.append(os.path.join(base_dir, filename))
        for p in possible_paths:
            if p and os.path.exists(p) and os.path.isfile(p):
                try:
                    os.remove(p)
                    break
                except Exception:
                    # 不影响主操作结果，只记录（若需要可改为日志）
                    pass
    except Exception:
        pass

    return jsonify({'success': True})