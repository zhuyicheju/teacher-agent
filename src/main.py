# ...existing code...
import os
from flask import Flask, request, jsonify, render_template, Response, session, redirect, url_for
from knowledge_processor import knowledge_processor_app
from rag_agent import rag_answer_stream, generate_title_sync  # 新增
import json  # 新增
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from pathlib import Path
from pathlib import Path
from datetime import datetime  # 新增
from vector_db import VectorDB  # 新增导入（如未导入）
from generate_title import generate_title_endpoint

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
app.add_url_rule('/generate_title', view_func=generate_title_endpoint, methods=['POST'])

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

def update_thread_title(thread_id: int, title: str):
    """直接更新 threads 表的 title 字段（如果 thread 模块已有函数可替换此实现）。"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute('UPDATE threads SET title = ? WHERE id = ?', (title, thread_id))
        conn.commit()
        conn.close()
    except Exception as e:
        print('更新线程标题失败：', e)

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

        # 如果没有提供 thread_id 则自动新建一个线程（先空标题，后由大模型生成并更新）
        generated_title = ''
        if not thread_id:
            # 先创建线程，空标题
            thread_id = create_thread(username, '')
            # 保存用户提问为消息（先保存，标题生成不影响消息）
            try:
                add_message(thread_id, username, 'user', question)
            except Exception as e:
                print("保存用户消息失败：", e)

            # 使用大模型对第一个问题生成简短会话标题
            try:
                generated_title = generate_title_sync(question, username=username, thread_id=thread_id, top_k=1)
                generated_title = (generated_title or '').strip().replace('\n',' ')
                if generated_title:
                    # 截断为合理长度
                    if len(generated_title) > 80:
                        generated_title = generated_title[:80].rstrip() + '...'
                    update_thread_title(thread_id, generated_title)
            except Exception as e:
                print('生成会话标题失败：', e)
        else:
            try:
                thread_id = int(thread_id)
            except Exception:
                return jsonify({'error': 'thread_id 格式错误'}), 400
            # 校验线程归属
            if not thread_belongs_to_user(thread_id, username):
                return jsonify({'error': '未找到线程或无权限'}), 404
            # 保存用户提问
            try:
                add_message(thread_id, username, 'user', question)
            except Exception as e:
                print("保存用户消息失败：", e)

        # 如果已存在生成的标题但前端/列表尚未刷新，会在后续 loadThreads 时显示新标题
        def generate():
            full_response = ''
            try:
                # 将 thread_id 传入 rag_answer_stream，要求 rag_agent 根据 thread_id 使用该会话的独立知识库
                for content in rag_answer_stream(question, username=username, top_k=5, thread_id=thread_id):
                    full_response += content
                    yield f"data: {json.dumps({'content': content})}\n\n"
                # 保存助手回答为消息
                try:
                    add_message(thread_id, username, 'assistant', full_response)
                except Exception as e:
                    print("保存助手消息失败：", e)
                # 返回 thread_id 与可能的标题（以便前端在需要时更新显示）
                meta = {'thread_id': thread_id}
                if generated_title:
                    meta['title'] = generated_title
                yield f"data: {json.dumps({'meta': meta})}\n\n"
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

@app.route('/admin_login', methods=['GET'])
def admin_login_page():
    # 渲染管理员登录页（可直接访问，实际登录凭据由后端校验）
    return render_template('admin_login.html')

@app.route('/admin_login', methods=['POST'])
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

@app.route('/logout', methods=['GET'])
def logout():
    session.pop('user', None)
    return redirect(url_for('login_page'))

# 新增：列出当前用户上传的文档（支持按 thread_id 过滤）
def list_user_documents(username: str, limit: int = 100, thread_id: int = None):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    if thread_id is None:
        # 未指定 thread_id 时，查询所有文件，返回时使用 original_filename（回退到 filename）
        cur.execute('SELECT id, COALESCE(original_filename, filename) as filename, stored_at, segment_count, thread_id FROM documents WHERE username = ? ORDER BY id DESC LIMIT ?', (username, limit))
    else:
        # 指定 thread_id 时，仅查询该会话的文件
        cur.execute('SELECT id, COALESCE(original_filename, filename) as filename, stored_at, segment_count, thread_id FROM documents WHERE username = ? AND thread_id = ? ORDER BY id DESC LIMIT ?', (username, thread_id, limit))
    rows = cur.fetchall()
    conn.close()
    return [{'id': r[0], 'filename': r[1], 'stored_at': r[2], 'segment_count': r[3], 'thread_id': r[4]} for r in rows]

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
    thread_id = request.args.get('thread_id')
    try:
        thread_id = int(thread_id) if thread_id not in (None, '', 'null') else None
    except Exception:
        thread_id = None
    items = list_user_documents(session.get('user'), thread_id=thread_id)
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

@app.route('/my_documents/<int:doc_id>', methods=['DELETE'])
def delete_my_document(doc_id):
    if not session.get('user'):
        return jsonify({'error': '未登录'}), 401
    username = session.get('user')

    # 可选来自前端的 thread_id（用于额外校验）
    q_thread = request.args.get('thread_id')
    try:
        q_thread = int(q_thread) if q_thread not in (None, '', 'null') else None
    except Exception:
        q_thread = None

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT id, username, filename, thread_id FROM documents WHERE id = ?', (doc_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify({'success': False, 'error': '未找到该文档'}), 404

    doc_owner = row[1]
    doc_thread = row[3]
    if doc_owner != username:
        conn.close()
        return jsonify({'success': False, 'error': '无权限删除该文档'}), 403

    # 如果前端提供了 thread_id，则强验证其与该文档的 thread_id 相同（加强会话隔离）
    if q_thread is not None and doc_thread is not None and int(q_thread) != int(doc_thread):
        conn.close()
        return jsonify({'success': False, 'error': '请求的会话与文档所属会话不匹配'}), 400

    # 获取该文档的所有 vector_id
    cur.execute('SELECT vector_id FROM document_segments WHERE document_id = ?', (doc_id,))
    rows = cur.fetchall()
    vector_ids = [r[0] for r in rows if r and r[0]]

    # 删除向量：选择对应命名空间（thread 独立命名）
    try:
        db = VectorDB(username=username, thread_id=doc_thread)
        if vector_ids:
            db.delete_documents(vector_ids)
    except Exception as e:
        # 若删除向量失败，记录但继续删除 DB 记录
        print("删除向量失败：", e)

    # 删除 DB 中 segments 与 document 记录
    try:
        cur.execute('DELETE FROM document_segments WHERE document_id = ?', (doc_id,))
        cur.execute('DELETE FROM documents WHERE id = ?', (doc_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({'success': False, 'error': f'删除数据库记录失败: {e}'}), 500

    conn.close()
    return jsonify({'success': True})

@app.route('/admin', methods=['GET'])
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

if __name__ == '__main__':
    app.run(debug=True)
# ...existing code...