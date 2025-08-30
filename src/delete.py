import os
import sqlite3
from flask import Blueprint, request, jsonify, session, current_app
from pathlib import Path
import shutil
import traceback
from vector_db import VectorDB

# 使用与项目一致的 DB_PATH 计算方式（不直接依赖 circular import）
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(base_dir, 'data', 'users.db')

delete_app = Blueprint('delete', __name__)

def document_belongs_to_user(doc_id: int, username: str):
    """
    返回 (filename, thread_id) 或 None
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT filename, thread_id FROM documents WHERE id = ? AND username = ?', (doc_id, username))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return (row[0], row[1])

@delete_app.route('/threads/<int:thread_id>', methods=['DELETE'])
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

@delete_app.route('/my_documents/<int:doc_id>', methods=['DELETE'])
def delete_document(doc_id):
    if not session.get('user'):
        return jsonify({'error': '未登录'}), 401
    username = session.get('user')
    # 验证文档归属并取得文件名与 thread_id（若有）
    res = document_belongs_to_user(doc_id, username)
    if res is None:
        return jsonify({'error': '未找到该文档或无权限'}), 404
    filename, doc_thread = res

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    try:
        # 获取该文档的所有 vector_id
        cur.execute('SELECT vector_id FROM document_segments WHERE document_id = ?', (doc_id,))
        rows = cur.fetchall()
        vector_ids = [r[0] for r in rows if r and r[0]]

        # 删除向量：选择对应命名空间（thread 独立命名）
        try:
            db = VectorDB(username=username, thread_id=doc_thread)
            if vector_ids:
                db.delete_documents(vector_ids)
        except Exception as e:
            print("删除向量失败：", e, traceback.format_exc())

        # 删除 DB 记录（先分段再文档）
        try:
            cur.execute('DELETE FROM document_segments WHERE document_id = ?', (doc_id,))
            cur.execute('DELETE FROM documents WHERE id = ? AND username = ?', (doc_id, username))
            conn.commit()
        except Exception as e:
            conn.rollback()
            conn.close()
            return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

    # 尝试从磁盘删除对应文件（如果能定位到）以及可能的原始路径
    try:
        # 如果 filename 是绝对路径，直接尝试删除；否则尝试常见上传目录及 raw_documents 路径
        possible_paths = []
        if filename and os.path.isabs(filename):
            possible_paths.append(filename)
        else:
            possible_paths.append(os.path.join(base_dir, 'uploads', filename))
            possible_paths.append(os.path.join(base_dir, 'data', 'uploads', filename))
            possible_paths.append(os.path.join(base_dir, filename))
            # raw_documents 路径（根据 username 与 thread）
            if username is not None:
                if doc_thread is not None:
                    possible_paths.append(os.path.join(base_dir, 'data', 'raw_documents', username, f"thread_{doc_thread}", filename))
                possible_paths.append(os.path.join(base_dir, 'data', 'raw_documents', username, filename))
        for p in possible_paths:
            if p and os.path.exists(p) and os.path.isfile(p):
                try:
                    os.remove(p)
                    break
                except Exception:
                    pass
    except Exception:
        pass

    return jsonify({'success': True})

# 新增：管理员列出所有线程
@delete_app.route('/admin/api/threads', methods=['GET'])
def admin_list_threads():
    if session.get('user') != 'admin':
        return jsonify({'error': '无权限'}), 403
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT id, username, title, created_at FROM threads ORDER BY id DESC')
    rows = cur.fetchall()
    conn.close()
    items = [{'id': r[0], 'username': r[1], 'title': r[2], 'created_at': r[3]} for r in rows]
    return jsonify({'items': items})

# 新增：管理员列出所有文档（可选按 thread_id 或 username 过滤）
@delete_app.route('/admin/api/documents', methods=['GET'])
def admin_list_documents():
    if session.get('user') != 'admin':
        return jsonify({'error': '无权限'}), 403
    thread_id = request.args.get('thread_id')
    username = request.args.get('username')
    try:
        thread_id = int(thread_id) if thread_id not in (None, '', 'null') else None
    except Exception:
        thread_id = None
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    q = 'SELECT id, username, COALESCE(original_filename, filename), stored_at, segment_count, thread_id FROM documents'
    conds = []
    params = []
    if username:
        conds.append('username = ?'); params.append(username)
    if thread_id is not None:
        conds.append('thread_id = ?'); params.append(thread_id)
    if conds:
        q += ' WHERE ' + ' AND '.join(conds)
    q += ' ORDER BY id DESC'
    cur.execute(q, params)
    rows = cur.fetchall()
    conn.close()
    items = [{'id': r[0], 'username': r[1], 'filename': r[2], 'stored_at': r[3], 'segment_count': r[4], 'thread_id': r[5]} for r in rows]
    return jsonify({'items': items})

# 新增：管理员删除任意线程（会同时删除向量、持久化目录、raw_documents、DB记录）
@delete_app.route('/admin/api/threads/<int:thread_id>', methods=['DELETE'])
def admin_delete_thread(thread_id):
    if session.get('user') != 'admin':
        return jsonify({'error': '无权限'}), 403

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # 查出线程所属用户（若不存在则返回404）
    cur.execute('SELECT username FROM threads WHERE id = ?', (thread_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify({'error': '未找到线程'}), 404
    username = row[0]

    try:
        # 获取该线程下文档 id
        cur.execute('SELECT id FROM documents WHERE thread_id = ? AND username = ?', (thread_id, username))
        docs = [r[0] for r in cur.fetchall()]

        # 收集 vector_id
        vector_ids = []
        if docs:
            cur.execute('SELECT vector_id FROM document_segments WHERE document_id IN ({seq})'.format(seq=','.join(['?']*len(docs))), docs)
            vector_ids = [r[0] for r in cur.fetchall() if r and r[0]]

        # 删除向量
        try:
            vdb = VectorDB(username=username, thread_id=thread_id)
            if vector_ids:
                vdb.delete_documents(vector_ids)
        except Exception as e:
            print("管理员删除向量失败：", e, traceback.format_exc())

        # 删除 persist 目录
        try:
            vdb = VectorDB(username=username, thread_id=thread_id)
            persist_dir = getattr(vdb, 'persist_directory', None)
            if persist_dir and os.path.isdir(persist_dir):
                shutil.rmtree(persist_dir, ignore_errors=True)
        except Exception as e:
            print("管理员移除 persist_directory 失败：", e)

        # 删除 raw_documents
        try:
            raw_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'raw_documents', username, f"thread_{thread_id}"))
            if os.path.isdir(raw_dir):
                shutil.rmtree(raw_dir, ignore_errors=True)
        except Exception as e:
            print("管理员移除 raw_documents 失败：", e)

        # 删除 DB 记录
        try:
            cur.execute('DELETE FROM messages WHERE thread_id = ?', (thread_id,))
            if docs:
                cur.execute('DELETE FROM document_segments WHERE document_id IN ({seq})'.format(seq=','.join(['?']*len(docs))), docs)
                cur.execute('DELETE FROM documents WHERE id IN ({seq})'.format(seq=','.join(['?']*len(docs))), docs)
            cur.execute('DELETE FROM threads WHERE id = ?', (thread_id,))
            conn.commit()
        except Exception as e:
            conn.rollback()
            conn.close()
            return jsonify({'error': f'删除数据库记录失败: {e}'}), 500

    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({'error': str(e)}), 500

    conn.close()
    return jsonify({'success': True})

# 新增：管理员删除任意文档（会同时删除向量与 DB 记录）
@delete_app.route('/admin/api/documents/<int:doc_id>', methods=['DELETE'])
def admin_delete_document(doc_id):
    if session.get('user') != 'admin':
        return jsonify({'error': '无权限'}), 403

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT id, username, filename, thread_id FROM documents WHERE id = ?', (doc_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify({'error': '未找到该文档'}), 404
    owner = row[1]
    doc_thread = row[3]

    try:
        cur.execute('SELECT vector_id FROM document_segments WHERE document_id = ?', (doc_id,))
        rows = cur.fetchall()
        vector_ids = [r[0] for r in rows if r and r[0]]

        try:
            db = VectorDB(username=owner, thread_id=doc_thread)
            if vector_ids:
                db.delete_documents(vector_ids)
        except Exception as e:
            print("管理员删除文档向量失败：", e, traceback.format_exc())

        try:
            cur.execute('DELETE FROM document_segments WHERE document_id = ?', (doc_id,))
            cur.execute('DELETE FROM documents WHERE id = ?', (doc_id,))
            conn.commit()
        except Exception as e:
            conn.rollback()
            conn.close()
            return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

    # 尝试删除源文件（raw_documents）
    try:
        raw_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'raw_documents', owner, f"thread_{doc_thread}", row[2]))
        if os.path.isfile(raw_path):
            try:
                os.remove(raw_path)
            except Exception:
                pass
    except Exception:
        pass

    return jsonify({'success': True})