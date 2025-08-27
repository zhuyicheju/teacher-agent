import os
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from pathlib import Path

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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
