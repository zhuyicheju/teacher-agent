from flask import session, jsonify, request

from cola.domain.factory.Repositoryfactory import documents_repository
from cola.domain.business.documentService import document_service as document_domain_service
class DocumentService:
    def __init__(self):
        self.ALLOWED_EXTENSIONS = {'pdf', 'docx'}

    #done
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

        ##透传入infra层
        items = document_domain_service.list_user_document_titles(user, thread_id=thread_id)
        return jsonify({'items': items})

    def delete_document(self, doc_id):
        if not session.get('user'):
            return jsonify({'error': '未登录'}), 401
        username = session.get('user')
        # 验证文档归属并取得文件名与 thread_id（若有）
        row = documents_repository.document_belongs_to_user(doc_id, username)

        if row is None:
            return jsonify({'error': '未找到该文档或无权限'}), 404
        filename = row[0]

        return document_domain_service.delete_document(username, doc_id, filename)

    def my_documents(self):
        if not session.get('user'):
            return jsonify({'error': '未登录'}), 401
        thread_id = request.args.get('thread_id')
        try:
            thread_id = int(thread_id) if thread_id not in (None, '', 'null') else None
        except Exception:
            thread_id = None
        items = document_domain_service.list_user_documents(session.get('user'), thread_id=thread_id)
        return jsonify({'items': items})

    def my_document_segments(self, doc_id):
        if not session.get('user'):
            return jsonify({'error': '未登录'}), 401
        segs = document_domain_service.get_document_segments(session.get('user'), doc_id)
        if segs is None:
            return jsonify({'error': '未找到该文档或无权限'}), 404
        return jsonify({'segments': segs})

    def delete_my_document(self, doc_id):
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

        thread_id = request.form.get('thread_id') or request.args.get('thread_id')
        try:
            thread_id = int(thread_id) if thread_id not in (None, '', 'null') else None
        except Exception:
            thread_id = None

        return document_domain_service.upload_document(user, file, thread_id)

document_service = DocumentService()