from flask import Blueprint, session, jsonify, request

bp_my_documents = Blueprint("my_documents", __name__)

@bp_my_documents.route('/my_documents/<int:doc_id>', methods=['DELETE'])
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

@bp_my_documents.route('/my_documents', methods=['GET'])
def my_documents():
    if not session.get('user'):
        return jsonify({'error': '未登录'}), 401
    thread_id = request.args.get('thread_id')
    try:
        thread_id = int(thread_id) if thread_id not in (None, '', 'null') else None
    except Exception:
        thread_id = None
    items = list_user_documents(session.get('user'), thread_id=thread_id)
    return jsonify({'items': items})

@bp_my_documents.route('/my_documents/<int:doc_id>/segments', methods=['GET'])
def my_document_segments(doc_id):
    if not session.get('user'):
        return jsonify({'error': '未登录'}), 401
    segs = get_document_segments(session.get('user'), doc_id)
    if segs is None:
        return jsonify({'error': '未找到该文档或无权限'}), 404
    return jsonify({'segments': segs})

@bp_my_documents.route('/my_documents/<int:doc_id>', methods=['DELETE'])
def delete_my_document(doc_id):
    if not session.get('user'):
        return jsonify({'error': '未登录'}), 401
    username = session.get('user')

    # 可选来自前端的 thread_id（用于额外校验）
    q_thread = request.args.get('thread_id')
    try:
        q_thread = int(q_thread) if q_thread not in (None, '', 'null') else None
    except Exception:
        q_thread = None

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT id, username, filename, thread_id FROM documents WHERE id = ?', (doc_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify({'success': False, 'error': '未找到该文档'}), 404

    doc_owner = row[1]
    doc_thread = row[3]
    if doc_owner != username:
        conn.close()
        return jsonify({'success': False, 'error': '无权限删除该文档'}), 403

    # 如果前端提供了 thread_id，则强验证其与该文档的 thread_id 相同（加强会话隔离）
    if q_thread is not None and doc_thread is not None and int(q_thread) != int(doc_thread):
        conn.close()
        return jsonify({'success': False, 'error': '请求的会话与文档所属会话不匹配'}), 400

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
        # 若删除向量失败，记录但继续删除 DB 记录
        print("删除向量失败：", e)

    # 删除 DB 中 segments 与 document 记录
    try:
        cur.execute('DELETE FROM document_segments WHERE document_id = ?', (doc_id,))
        cur.execute('DELETE FROM documents WHERE id = ?', (doc_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({'success': False, 'error': f'删除数据库记录失败: {e}'}), 500

    conn.close()
    return jsonify({'success': True})