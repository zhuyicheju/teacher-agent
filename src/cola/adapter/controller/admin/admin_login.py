from flask import Blueprint, jsonify, session, request, render_template

bp_admin_login = Blueprint("admin_login", __name__)

@bp_admin_login.route('/admin_login', methods=['GET'])
def admin_login_page():
    # 渲染管理员登录页（可直接访问，实际登录凭据由后端校验）
    return render_template('admin_login.html')

@bp_admin_login.route('/admin_login', methods=['POST'])
def admin_login_api():
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