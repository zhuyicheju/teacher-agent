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

# -------- 用户数据库配置（SQLite） --------
DB_PATH = os.path.join(base_dir, 'data', 'users.db')

def init_db():
    Path(os.path.dirname(DB_PATH)).mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    ''')
    # 新：thread 表表示独立对话会话（每个会话可包含多条消息）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS threads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            title TEXT,
            created_at TEXT NOT NULL
        )
    ''')
    # 新：messages 表保存每条消息（role: user/assistant）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(thread_id) REFERENCES threads(id)
        )
    ''')
    conn.commit()
    conn.close()

def create_user(username: str, password: str):
    if not username or not password:
        return False, "用户名或密码不能为空"
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO users (username, password_hash) VALUES (?, ?)',
            (username, generate_password_hash(password))
        )
        conn.commit()
        return True, None
    except sqlite3.IntegrityError:
        return False, "用户名已存在"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def verify_user(username: str, password: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT password_hash FROM users WHERE username = ?', (username,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return False
    return check_password_hash(row[0], password)

# 初始化数据库
init_db()

# -------- 原有路由（首页 + 问答流） --------
@app.route('/')
def index():
    # 登录保护：未登录则跳转到登录页
    if not session.get('user'):
        return redirect(url_for('login_page'))
    return render_template('index.html', user=session.get('user'))

# 新增：线程 / 消息 操作
def create_thread(username: str, title: str = None) -> int:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('INSERT INTO threads (username, title, created_at) VALUES (?, ?, ?)',
                (username, title or '', datetime.utcnow().isoformat()))
    thread_id = cur.lastrowid
    conn.commit()
    conn.close()
    return thread_id

# 新增：校验线程是否属于某用户
def thread_belongs_to_user(thread_id: int, username: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT 1 FROM threads WHERE id = ? AND username = ?', (thread_id, username))
    ok = cur.fetchone() is not None
    conn.close()
    return ok

def list_threads(username: str, limit: int = 100):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT id, title, created_at FROM threads WHERE username = ? ORDER BY id DESC LIMIT ?', (username, limit))
    rows = cur.fetchall()
    conn.close()
    return [{'id': r[0], 'title': r[1], 'created_at': r[2]} for r in rows]

# 加强：写消息前校验线程归属，防止写入到其它会话
def add_message(thread_id: int, username: str, role: str, content: str):
    if not thread_belongs_to_user(thread_id, username):
        raise ValueError("线程不存在或不属于当前用户")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('INSERT INTO messages (thread_id, username, role, content, created_at) VALUES (?, ?, ?, ?, ?)',
                (thread_id, username, role, content, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()

# 读取时同时按 thread_id + username 过滤，双重保证
def get_thread_messages(username: str, thread_id: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # 确保线程属于当前用户
    cur.execute('SELECT id FROM threads WHERE id = ? AND username = ?', (thread_id, username))
    if not cur.fetchone():
        conn.close()
        return None
    # 只返回该用户在该线程的消息（防止其他意外写入）
    cur.execute('SELECT id, role, content, created_at FROM messages WHERE thread_id = ? AND username = ? ORDER BY id ASC', (thread_id, username))
    rows = cur.fetchall()
    conn.close()
    return [{'id': r[0], 'role': r[1], 'content': r[2], 'created_at': r[3]} for r in rows]

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

# 新增线程管理 API
@app.route('/threads', methods=['GET'])
def threads_list():
    if not session.get('user'):
        return jsonify({'error': '未登录'}), 401
    items = list_threads(session.get('user'))
    return jsonify({'items': items})

@app.route('/threads', methods=['POST'])
def threads_create():
    if not session.get('user'):
        return jsonify({'error': '未登录'}), 401
    data = request.get_json(silent=True) or request.form
    title = (data.get('title') or '').strip()
    tid = create_thread(session.get('user'), title)
    return jsonify({'thread_id': tid})

@app.route('/threads/<int:thread_id>/messages', methods=['GET'])
def thread_messages(thread_id):
    if not session.get('user'):
        return jsonify({'error': '未登录'}), 401
    msgs = get_thread_messages(session.get('user'), thread_id)
    if msgs is None:
        return jsonify({'error': '未找到线程或无权限'}), 404
    return jsonify({'messages': msgs})

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