from flask import session, jsonify, request

class DocumentService:
    def __init__(self):
        pass

    def knowledge_titles(self):
        """
        API: /knowledge_titles?thread_id=<id>
        返回当前登录用户已上传知识文档的标题列表（仅文件名作为标题）。
        支持可选的 thread_id 参数用于仅显示该会话下的知识（会话隔离）。
        """
        user = session.get('user')
        if not user:
            return jsonify({"error": "未登录"}), 401

        thread_id = request.args.get('thread_id')
        try:
            thread_id = int(thread_id) if thread_id not in (None, '', 'null') else None
        except Exception:
            thread_id = None

        items = list_user_document_titles(user, thread_id=thread_id)
        return jsonify({'items': items})

    def delete_document(self, doc_id):
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
                        possible_paths.append(
                            os.path.join(base_dir, 'data', 'raw_documents', username, f"thread_{doc_thread}", filename))
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

    def my_documents(self):
        if not session.get('user'):
            return jsonify({'error': '未登录'}), 401
        thread_id = request.args.get('thread_id')
        try:
            thread_id = int(thread_id) if thread_id not in (None, '', 'null') else None
        except Exception:
            thread_id = None
        items = list_user_documents(session.get('user'), thread_id=thread_id)
        return jsonify({'items': items})

    def my_document_segments(self, doc_id):
        if not session.get('user'):
            return jsonify({'error': '未登录'}), 401
        segs = get_document_segments(session.get('user'), doc_id)
        if segs is None:
            return jsonify({'error': '未找到该文档或无权限'}), 404
        return jsonify({'segments': segs})

    def delete_my_document(self, doc_id):
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

    def upload_file(self):
        # 必须登录
        user = session.get('user')
        if not user:
            return jsonify({"error": "未登录"}), 401

        if 'file' not in request.files:
            return jsonify({"error": "未发现上传文件"}), 400

        file = request.files['file']
        if not file or file.filename == '':
            return jsonify({"error": "文件名为空"}), 400

        # 保存原始文件名（未经 secure_filename 改写）
        original_filename = file.filename

        # 使用安全文件名并检查扩展
        filename = secure_filename(file.filename)
        if not allowed_file(filename):
            return jsonify({"error": f"不支持的文件类型，仅支持: {', '.join(sorted(ALLOWED_EXTENSIONS))}"}), 400

        # 支持可选的 thread_id（表单字段或查询字符串）
        thread_id = request.form.get('thread_id') or request.args.get('thread_id')
        try:
            thread_id = int(thread_id) if thread_id not in (None, '', 'null') else None
        except Exception:
            thread_id = None

        # 修改：按用户和会话分层存储文件
        raw_documents_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw_documents')
        user_dir = os.path.join(raw_documents_dir, user)
        thread_dir = os.path.join(user_dir, f"thread_{thread_id}" if thread_id else "no_thread")
        try:
            os.makedirs(thread_dir, exist_ok=True)
        except Exception as e:
            tb = traceback.format_exc()
            logger.error("创建存储目录失败: %s\n%s", str(e), tb)
            return jsonify({"error": "服务器无法创建存储目录", "detail": str(e)}), 500

        file_path = os.path.join(thread_dir, filename)
        try:
            file.save(file_path)
        except Exception as e:
            tb = traceback.format_exc()
            logger.error("保存上传文件失败: %s\n%s", str(e), tb)
            return jsonify({"error": "保存上传文件失败", "detail": str(e)}), 500

        try:
            processed_segments = process_uploaded_document(file_path)
        except Exception as e:
            tb = traceback.format_exc()
            logger.error("读取或分割文档失败: %s\n%s", str(e), tb)
            return jsonify({"error": "读取或分割文档失败", "detail": str(e)}), 500

        vector_error = None
        stored_ids = []
        doc_id = None
        try:
            # 使用按用户/会话隔离的 VectorDB（传入 username 与 thread_id）
            db = VectorDB(username=user, thread_id=thread_id)
            # metadata 包含 username、source_file、thread_id 与 segment_index
            metadatas = [
                {"username": user, "source_file": original_filename, "thread_id": thread_id, "segment_index": i + 1} for
                i in range(len(processed_segments))]
            # ids 加入 user/thread 信息以便唯一识别
            if thread_id is not None:
                ids = [f"{user}__thread_{thread_id}__{os.path.splitext(filename)[0]}_seg_{i + 1:04d}" for i in
                       range(len(processed_segments))]
            else:
                ids = [f"{user}__{os.path.splitext(filename)[0]}_seg_{i + 1:04d}" for i in
                       range(len(processed_segments))]
            stored_ids = db.add_documents(processed_segments, metadatas=metadatas, ids=ids)

            # 在 users.db 中记录 document 与 segments（包含 thread_id），同时保存 original_filename
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            # 适配可能不存在 original_filename 列的旧 DB（ensure_docs_tables 已添加列，但以防）
            try:
                cur.execute(
                    'INSERT INTO documents (username, filename, original_filename, stored_at, segment_count, thread_id) VALUES (?, ?, ?, ?, ?, ?)',
                    (user, filename, original_filename, datetime.utcnow().isoformat(), len(processed_segments),
                     thread_id))
            except Exception:
                # 退回到没有 original_filename 列的插入（兼容性）
                cur.execute(
                    'INSERT INTO documents (username, filename, stored_at, segment_count, thread_id) VALUES (?, ?, ?, ?, ?)',
                    (user, filename, datetime.utcnow().isoformat(), len(processed_segments), thread_id))
                # 尝试更新 original_filename 列（若存在）
                try:
                    doc_id_temp = cur.lastrowid
                    cur.execute('UPDATE documents SET original_filename = ? WHERE id = ?',
                                (original_filename, doc_id_temp))
                except Exception:
                    pass

            doc_id = cur.lastrowid
            for idx, vid in enumerate(stored_ids, start=1):
                preview = processed_segments[idx - 1][:200]
                cur.execute(
                    'INSERT INTO document_segments (document_id, segment_index, vector_id, preview) VALUES (?, ?, ?, ?)',
                    (doc_id, idx, vid, preview))
            conn.commit()
            conn.close()

        except Exception as e:
            # 记录完整堆栈到日志，便于排查 VectorDB/Chroma/嵌入相关的问题
            tb = traceback.format_exc()
            logger.error("向量化或写入数据库失败: %s\n%s", str(e), tb)
            vector_error = str(e)

        # 根据是否创建了 documents 记录返回 success 标志与文档信息
        success = doc_id is not None
        document_info = None
        if success:
            # 返回给前端的 filename 字段使用原始文件名（未被 secure_filename 改写）
            document_info = {
                "id": doc_id,
                "username": user,
                "filename": original_filename,
                "stored_at": datetime.utcnow().isoformat(),
                "segment_count": len(processed_segments),
                "thread_id": thread_id
            }

        # 若在向量化阶段出现错误，返回 500 并携带 vector_error（前端可显示给开发人员）
        status_code = 200 if success else 500
        resp = {
            "success": success,
            "message": "上传完成" if success else "上传失败（详见 vector_error 或后端日志）",
            "document": document_info,
            "segments": processed_segments,
            "stored_ids": stored_ids,
            "vector_error": vector_error
        }
        # 开发者可通过设置环境变量 DEV_MODE=1 来在响应中包含更多调试信息（例如日志位置）
        if os.environ.get('DEV_MODE') == '1' and not success:
            resp['_debug_log'] = os.path.join(LOG_DIR, 'upload_errors.log')
        return jsonify(resp), status_code

document_service = DocumentService()