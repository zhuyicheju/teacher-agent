from flask import Blueprint, session, redirect, render_template, url_for

bp_index = Blueprint("index", __name__)

@bp_index.route('/')
def index():
    # 登录保护：未登录则跳转到登录页
    if not session.get('user'):
        return redirect(url_for('login_page'))
    return render_template('index.html', user=session.get('user'))
    ##这种情况如果下沉到app层麻烦许多，暂时不实现
    ##未来会前后端分离