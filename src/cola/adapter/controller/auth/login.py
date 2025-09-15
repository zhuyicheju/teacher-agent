from flask import Blueprint, session, jsonify, request, render_template
from cola.application.service.authService import auth_service


bp_login = Blueprint("login", __name__)

##后续前后端分离
@bp_login.route('/login', methods=['GET'])
def login_page():
    return render_template('login.html')

@bp_login.route('/login', methods=['POST'])
def login_api():
    return auth_service.login()