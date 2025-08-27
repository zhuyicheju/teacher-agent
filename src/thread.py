import os
import sqlite3
from flask import Blueprint, request, jsonify, session
from pathlib import Path
from datetime import datetime

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(base_dir, 'data', 'users.db')

thread_app = Blueprint('threads', __name__)

def init_thread_db(db_path: str = DB_PATH):
    Path(os.path.dirname(db_path)).mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS threads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            title TEXT,
            created_at TEXT NOT NULL
        )
    ''')
    cur.execute('''
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

def create_thread(username: str, title: str = None) -> int:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('INSERT INTO threads (username, title, created_at) VALUES (?, ?, ?)',
                (username, title or '', datetime.utcnow().isoformat()))
    thread_id = cur.lastrowid
    conn.commit()
    conn.close()
    return thread_id

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

def add_message(thread_id: int, username: str, role: str, content: str):
    if not thread_belongs_to_user(thread_id, username):
        raise ValueError("线程不存在或不属于当前用户")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('INSERT INTO messages (thread_id, username, role, content, created_at) VALUES (?, ?, ?, ?, ?)',
                (thread_id, username, role, content, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()

def get_thread_messages(username: str, thread_id: int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT id FROM threads WHERE id = ? AND username = ?', (thread_id, username))
    if not cur.fetchone():
        conn.close()
        return None
    cur.execute('SELECT id, role, content, created_at FROM messages WHERE thread_id = ? AND username = ? ORDER BY id ASC', (thread_id, username))
    rows = cur.fetchall()
    conn.close()
    return [{'id': r[0], 'role': r[1], 'content': r[2], 'created_at': r[3]} for r in rows]

# Blueprint routes: main.py 会注册这个 Blueprint
@thread_app.route('/threads', methods=['GET'])
def threads_list():
    if not session.get('user'):
        return jsonify({'error': '未登录'}), 401
    items = list_threads(session.get('user'))
    return jsonify({'items': items})

@thread_app.route('/threads', methods=['POST'])
def threads_create():
    if not session.get('user'):
        return jsonify({'error': '未登录'}), 401
    data = request.get_json(silent=True) or request.form
    title = (data.get('title') or '').strip()
    tid = create_thread(session.get('user'), title)
    return jsonify({'thread_id': tid})

@thread_app.route('/threads/<int:thread_id>/messages', methods=['GET'])
def thread_messages(thread_id):
    if not session.get('user'):
        return jsonify({'error': '未登录'}), 401
    msgs = get_thread_messages(session.get('user'), thread_id)
    if msgs is None:
        return jsonify({'error': '未找到线程或无权限'}), 404
    return jsonify({'messages': msgs})
