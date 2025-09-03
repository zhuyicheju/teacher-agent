from flask import Blueprint, session, redirect, url_for

bp_logout = Blueprint("logout", __name__)

## 后续前后端分离
@bp_logout.route('/logout', methods=['GET'])
def logout():
    session.pop('user', None)
    return redirect(url_for('login_page'))