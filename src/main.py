# ...existing code...
import os
from flask import Flask, request, jsonify, render_template, Response, session, redirect, url_for
from knowledge_processor import knowledge_processor_app
from rag_agent import rag_answer_stream  # 新增
import json  # 新增
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from pathlib import Path
from pathlib import Path
from datetime import datetime  # 新增

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
template_path = os.path.join(base_dir, 'templates')
static_path = os.path.join(base_dir, 'static')

app = Flask(__name__, 
            template_folder=template_path,
            static_folder=static_path)

# 设置 secret_key（开发环境用，可从环境变量设置更安全）
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret')

# 注册 knowledge_processor 的 Blueprint
app.register_blueprint(knowledge_processor_app)

# -------- 用户数据库配置与用户函数已移至 src/init.py --------
# 从 init 模块导入 DB_PATH 与用户相关函数
from init import DB_PATH, init_db, create_user, verify_user

# 初始化用户数据库（如果需要）
init_db()

# 从新的 thread 模块导入线程相关的 Blueprint 与函数，并初始化线程表
from thread import (
    thread_app,
    create_thread,
    add_message,
    thread_belongs_to_user,
    list_threads,
    get_thread_messages,
    init_thread_db
)

# 新增：导入并注册删除功能的 Blueprint
from delete import delete_app

# 注册线程 Blueprint
app.register_blueprint(thread_app)

# 注册删除 Blueprint（包含 /threads/<id> DELETE 与 /my_documents/<id> DELETE）
app.register_blueprint(delete_app)

# 确保线程/消息表存在
init_thread_db(DB_PATH)

# -------- 原有路由（首页 + 问答流） --------
@app.route('/')
def index():
    # 登录保护：未登录则跳转到登录页
    if not session.get('user'):
        return redirect(url_for('login_page'))
    return render_template('index.html', user=session.get('user'))

@app.route('/ask', methods=['POST', 'GET'])
def ask_stream():
    # 后端再做一次登录校验（防止直接访问）
    if not session.get('user'):
        return jsonify({'error': '未登录，请先登录'}), 401

    try:
        username = session.get('user')
        if request.method == 'POST':
            data = request.get_json() or {}
            question = data.get('question', '')
            thread_id = data.get('thread_id')  # 支持 POST 指定 thread
        else:
            question = request.args.get('question', '')
            thread_id = request.args.get('thread_id')  # 支持 GET(EventSource) 指定 thread
        
        if not question:
            return jsonify({'error': '问题不能为空'}), 400

        # 如果没有提供 thread_id 则自动新建一个线程（title 简短取自问题）
        if not thread_id:
            title = (question[:80] + '...') if len(question) > 80 else question
            thread_id = create_thread(username, title)
        else:
            try:
                thread_id = int(thread_id)
            except Exception:
                return jsonify({'error': 'thread_id 格式错误'}), 400
            # 新增校验：确保该 thread 属于当前用户
            if not thread_belongs_to_user(thread_id, username):
                return jsonify({'error': '未找到线程或无权限'}), 404

        # 先保存用户提问（作为消息）
        try:
            add_message(thread_id, username, 'user', question)
        except Exception as e:
            print("保存用户消息失败：", e)

        # 如果需要将历史消息作为上下文，可在此读取并拼接（目前不自动拼接，保留单问答RAG）
        def generate():
            full_response = ''
            try:
                for content in rag_answer_stream(question, username=username, top_k=5):
                    full_response += content
                    yield f"data: {json.dumps({'content': content})}\n\n"
                # 保存助手回答为消息
                try:
                    add_message(thread_id, username, 'assistant', full_response)
                except Exception as e:
                    print("保存助手消息失败：", e)
                # 返回 thread_id 以便前端跟踪（最后一条返回）
                yield f"data: {json.dumps({'meta': {'thread_id': thread_id}})}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                yield "data: [DONE]\n\n"

        return Response(generate(), mimetype='text/event-stream')
        
    except Exception as e:
        print("错误信息:", e)
        return jsonify({'error': '服务器内部错误，请稍后再试！'}), 500

# -------- 注册 / 登录 页面与接口 --------
@app.route('/register', methods=['GET'])
def register_page():
    return render_template('register.html')

@app.route('/register', methods=['POST'])
def register_api():
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

@app.route('/login', methods=['GET'])
def login_page():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login_api():
    data = request.get_json(silent=True) or request.form
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    if verify_user(username, password):
        session['user'] = username
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': '用户名或密码错误'}), 401

@app.route('/logout', methods=['GET'])
def logout():
    session.pop('user', None)
    return redirect(url_for('login_page'))

# 新增：列出当前用户上传的文档
def list_user_documents(username: str, limit: int = 100):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT id, filename, stored_at, segment_count FROM documents WHERE username = ? ORDER BY id DESC LIMIT ?', (username, limit))
    rows = cur.fetchall()
    conn.close()
    return [{'id': r[0], 'filename': r[1], 'stored_at': r[2], 'segment_count': r[3]} for r in rows]

# 新增：获取某个文档的分段（确保归属）
def get_document_segments(username: str, document_id: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # 验证文档属于该用户
    cur.execute('SELECT id FROM documents WHERE id = ? AND username = ?', (document_id, username))
    if not cur.fetchone():
        conn.close()
        return None
    cur.execute('SELECT segment_index, vector_id, preview FROM document_segments WHERE document_id = ? ORDER BY segment_index ASC', (document_id,))
    rows = cur.fetchall()
    conn.close()
    return [{'index': r[0], 'vector_id': r[1], 'preview': r[2]} for r in rows]

# 新增接口：返回当前用户已上传文档列表
@app.route('/my_documents', methods=['GET'])
def my_documents():
    if not session.get('user'):
        return jsonify({'error': '未登录'}), 401
    items = list_user_documents(session.get('user'))
    return jsonify({'items': items})

# 新增接口：返回指定文档的分段
@app.route('/my_documents/<int:doc_id>/segments', methods=['GET'])
def my_document_segments(doc_id):
    if not session.get('user'):
        return jsonify({'error': '未登录'}), 401
    segs = get_document_segments(session.get('user'), doc_id)
    if segs is None:
        return jsonify({'error': '未找到该文档或无权限'}), 404
    return jsonify({'segments': segs})

if __name__ == '__main__':
    app.run(debug=True)
# ...existing code...