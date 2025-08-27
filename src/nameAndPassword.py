# ...existing code...
import os
import sqlite3
import sys
from pathlib import Path
from werkzeug.security import check_password_hash

# 默认指向项目 data/users.db
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'users.db')

def list_users(db_path: str = DB_PATH):
    """
    返回 users 表中的所有用户（包含 password_hash）。
    注意：密码以哈希形式存储，不是明文。
    """
    if not Path(db_path).exists():
        return []
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT id, username, password_hash FROM users")
    rows = cur.fetchall()
    conn.close()
    return [{'id': r[0], 'username': r[1], 'password_hash': r[2]} for r in rows]

def print_users(db_path: str = DB_PATH):
    users = list_users(db_path)
    if not users:
        print("未找到任何用户或数据库不存在：", db_path)
        return
    print("id\tusername\tpassword_hash")
    for u in users:
        print(f"{u['id']}\t{u['username']}\t{u['password_hash']}")

def verify_user_password(username: str, password: str, db_path: str = DB_PATH) -> bool:
    """
    校验给定用户名和明文密码是否匹配（使用存储的哈希）。
    """
    if not Path(db_path).exists():
        return False
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT password_hash FROM users WHERE username = ?", (username,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return False
    return check_password_hash(row[0], password)

if __name__ == '__main__':
    # 用法：
    #   列表用户: python src/nameAndPassword.py
    #   校验用户: python src/nameAndPassword.py verify <username> <password>
    if len(sys.argv) >= 2 and sys.argv[1] == 'verify':
        if len(sys.argv) != 4:
            print("用法: python src/nameAndPassword.py verify <username> <password>")
            sys.exit(2)
        ok = verify_user_password(sys.argv[2], sys.argv[3])
        print("验证通过" if ok else "验证失败")
    else:
        print_users()
# ...existing code...