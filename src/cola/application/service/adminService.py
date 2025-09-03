from flask import session, jsonify, request

class AdminService:
    def __init__(self):
        pass

    def list_threads(self):
        if session.get('user') != 'admin':
            return jsonify({'error': '无权限'}), 403
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute('SELECT id, username, title, created_at FROM threads ORDER BY id DESC')
        rows = cur.fetchall()
        conn.close()
        items = [{'id': r[0], 'username': r[1], 'title': r[2], 'created_at': r[3]} for r in rows]
        return jsonify({'items': items})

    def list_documents(self):
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
            conds.append('username = ?');
            params.append(username)
        if thread_id is not None:
            conds.append('thread_id = ?');
            params.append(thread_id)
        if conds:
            q += ' WHERE ' + ' AND '.join(conds)
        q += ' ORDER BY id DESC'
        cur.execute(q, params)
        rows = cur.fetchall()
        conn.close()
        items = [{'id': r[0], 'username': r[1], 'filename': r[2], 'stored_at': r[3], 'segment_count': r[4],
                  'thread_id': r[5]} for r in rows]
        return jsonify({'items': items})

    def delete_thread(self, thread_id):
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
                cur.execute('SELECT vector_id FROM document_segments WHERE document_id IN ({seq})'.format(
                    seq=','.join(['?'] * len(docs))), docs)
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
                raw_dir = os.path.abspath(
                    os.path.join(os.path.dirname(__file__), '..', 'data', 'raw_documents', username,
                                 f"thread_{thread_id}"))
                if os.path.isdir(raw_dir):
                    shutil.rmtree(raw_dir, ignore_errors=True)
            except Exception as e:
                print("管理员移除 raw_documents 失败：", e)

            # 删除 DB 记录
            try:
                cur.execute('DELETE FROM messages WHERE thread_id = ?', (thread_id,))
                if docs:
                    cur.execute('DELETE FROM document_segments WHERE document_id IN ({seq})'.format(
                        seq=','.join(['?'] * len(docs))), docs)
                    cur.execute('DELETE FROM documents WHERE id IN ({seq})'.format(seq=','.join(['?'] * len(docs))),
                                docs)
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

    def delete_document(self, doc_id):
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
            raw_path = os.path.abspath(
                os.path.join(os.path.dirname(__file__), '..', 'data', 'raw_documents', owner, f"thread_{doc_thread}",
                             row[2]))
            if os.path.isfile(raw_path):
                try:
                    os.remove(raw_path)
                except Exception:
                    pass
        except Exception:
            pass

        return jsonify({'success': True})

    def admin_login(self):
        # 支持 JSON 或表单提交
        if request.is_json:
            data = request.get_json(silent=True) or {}
        else:
            data = request.form or {}
        username = (data.get('username') or '').strip()
        password = data.get('password') or ''
        # 仅允许 admin 用户通过此入口登录为管理员
        if username != 'admin':
            return jsonify({'success': False, 'error': '仅允许管理员账户'}), 403
        try:
            if verify_user(username, password):
                session['user'] = 'admin'
                return jsonify({'success': True})
            else:
                return jsonify({'success': False, 'error': '用户名或密码错误'}), 401
        except Exception as e:
            return jsonify({'success': False, 'error': '验证失败'}), 500

admin_service = AdminService()