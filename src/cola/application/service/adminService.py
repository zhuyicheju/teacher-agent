import traceback

from flask import session, jsonify, request
from cola.domain.business.authService import auth_service
from cola.domain.factory.Repositoryfactory import thread_repository, documents_repository, document_segments_repository, message_repository

class AdminService:
    def __init__(self):
        pass

    def list_threads(self):
        if session.get('user') != 'admin':
            return jsonify({'error': '无权限'}), 403

        ## application层透传infrastructure层
        rows = thread_repository.list_threads()
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

        rows = documents_repository.list_documents(username, thread_id)
        items = [{'id': r[0], 'username': r[1], 'filename': r[2], 'stored_at': r[3], 'segment_count': r[4],
                  'thread_id': r[5]} for r in rows]
        return jsonify({'items': items})

    def delete_thread(self, thread_id):
        if session.get('user') != 'admin':
            return jsonify({'error': '无权限'}), 403

        row = thread_repository.get_thread_username(thread_id)
        if not row:
            return jsonify({'error': '未找到线程'}), 404
        username = row[0]

        try:
            row = documents_repository.list_documents(username, thread_id)
            docs = [r[0] for r in row]

            row = document_segments_repository.get_vector_ids_by_docs(docs)
            vector_ids = [r[0] for r in row if r and r[0]]

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
                message_repository.delete_message_repository(thread_id)
                if docs:
                    document_segments_repository.delete_segments_by_docs(docs)
                    documents_repository.delete_documents(docs)
                thread_repository.delete_thread(thread_id)
                ## 组合成事务
            except Exception as e:
                ##回滚
                return jsonify({'error': f'删除数据库记录失败: {e}'}), 500

        except Exception as e:
            ## 回滚
            return jsonify({'error': str(e)}), 500

        return jsonify({'success': True})

    def delete_document(self, doc_id):
        if session.get('user') != 'admin':
            return jsonify({'error': '无权限'}), 403

        row = documents_repository.get_document_info(doc_id)
        if not row:
            return jsonify({'error': '未找到该文档'}), 404
        owner = row[1]
        doc_thread = row[3]

        try:
            rows = document_segments_repository.get_vector_ids_by_docs(doc_thread)
            vector_ids = [r[0] for r in rows if r and r[0]]

            try:
                db = VectorDB(username=owner, thread_id=doc_thread)
                if vector_ids:
                    db.delete_documents(vector_ids)
            except Exception as e:
                print("管理员删除文档向量失败：", e, traceback.format_exc())

            try:
                document_segments_repository.delete_segments_by_doc(doc_id)
                documents_repository.delete_documents(doc_id)
                ##事务
            except Exception as e:
                ##回滚
                return jsonify({'error': str(e)}), 500

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
        data = request.get_json(silent=True) or request.form
        username = (data.get('username') or '').strip()
        password = data.get('password') or ''
        if username != 'admin':
            return jsonify({'success': False, 'error': '仅允许管理员账户'}), 403
        try:
            if auth_service.verify_user(username, password):
                session['user'] = 'admin'
                return jsonify({'success': True})
            else:
                return jsonify({'success': False, 'error': '用户名或密码错误'}), 401
        except Exception as e:
            return jsonify({'success': False, 'error': '验证失败'}), 500

admin_service = AdminService()