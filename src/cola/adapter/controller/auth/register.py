from flask import Blueprint, render_template
from cola.application.service.authService import auth_service

bp_register = Blueprint("register", __name__)

##前后端分离
@bp_register.route('/register', methods=['GET'])
def register_page():
    return render_template('register.html')

@bp_register.route('/register', methods=['POST'])
def register_api():
    return auth_service.register()