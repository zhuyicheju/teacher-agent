from flask import Blueprint, render_template
from cola.application.service.adminService import admin_service

bp_admin_login = Blueprint("admin_login", __name__)


##前后端分离
@bp_admin_login.route('/admin_login', methods=['GET'])
def admin_login_page():
    # 渲染管理员登录页（可直接访问，实际登录凭据由后端校验）
    return render_template('admin_login.html')

@bp_admin_login.route('/admin_login', methods=['POST'])
def admin_login_api():
    return admin_service.admin_login()