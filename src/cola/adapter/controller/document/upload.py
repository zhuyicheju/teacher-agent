from flask import Blueprint, session, jsonify, request
from cola.application.service.documentService import document_service

bp_upload = Blueprint("upload", __name__)


@bp_upload.route('/upload', methods=['POST'])
def upload_file():
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

    return document_service.upload_file(user, file, thread_id)