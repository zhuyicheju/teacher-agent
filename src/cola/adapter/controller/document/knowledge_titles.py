from flask import Blueprint, session, jsonify, request

bp_knowledge_titles = Blueprint("knowledge_titles", __name__)

@bp_knowledge_titles.route('/knowledge_titles', methods=['GET'])
def knowledge_titles():
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