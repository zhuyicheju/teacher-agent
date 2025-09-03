from flask import jsonify, session, request
class AuthService:
    def __init__(self):
        pass

    def login(self):
        data = request.get_json(silent=True) or request.form
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        if verify_user(username, password):
            session['user'] = username
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': '用户名或密码错误'}), 401

    def register(self):
        # 支持 JSON 或表单
        data = request.get_json(silent=True) or request.form
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        ok, err = create_user(username, password)
        if ok:
            # 注册成功后直接登录
            session['user'] = username
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': err}), 400

auth_service = AuthService()