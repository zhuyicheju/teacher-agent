from flask import Blueprint, jsonify, session, redirect, url_for, request

bp_admin = Blueprint("admin", __name__)

@bp_admin.route('/admin/api/threads', methods=['GET'])
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
@bp_admin.route('/admin/api/documents', methods=['GET'])
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
@bp_admin.route('/admin/api/threads/<int:thread_id>', methods=['DELETE'])
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
@bp_admin.route('/admin/api/documents/<int:doc_id>', methods=['DELETE'])
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

@bp_admin.route('/admin', methods=['GET'])
def admin_page():
    # 仅 admin 用户可访问该页面
    if session.get('user') != 'admin':
        return redirect(url_for('index'))
    # 返回简单 HTML（依赖 static/js/app.js 中的 openAdminPanel 实现）
    return """
    <!doctype html>
    <html>
    <head><meta charset="utf-8"><title>管理员界面</title></head>
    <body>
      <div id="admin-root"></div>
      <div id="admin-output"></div>
      <script src="/static/js/app.js"></script>
      <script>
        // 等待 app.js 注册 openAdminPanel 后调用
        (function waitAndOpen(){
          if (window.openAdminPanel) window.openAdminPanel();
          else setTimeout(waitAndOpen, 150);
        })();
      </script>
    </body>
    </html>
    """