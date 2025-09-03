from flask import Blueprint, jsonify, session, redirect, url_for, request
from cola.application.service.adminService import admin_service


bp_admin = Blueprint("admin", __name__)

@bp_admin.route('/admin/api/threads', methods=['GET'])
def admin_list_threads():
    return admin_service.list_threads()

# 新增：管理员列出所有文档（可选按 thread_id 或 username 过滤）
@bp_admin.route('/admin/api/documents', methods=['GET'])
def admin_list_documents():
    return admin_service.list_documents()

# 新增：管理员删除任意线程（会同时删除向量、持久化目录、raw_documents、DB记录）
@bp_admin.route('/admin/api/threads/<int:thread_id>', methods=['DELETE'])
def admin_delete_thread(thread_id):
    return admin_service.delete_thread(thread_id)

# 新增：管理员删除任意文档（会同时删除向量与 DB 记录）
@bp_admin.route('/admin/api/documents/<int:doc_id>', methods=['DELETE'])
def admin_delete_document(doc_id):
    return admin_service.delete_document(doc_id)


##前后端分离
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