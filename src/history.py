import os
import sqlite3
from pathlib import Path
from typing import List, Dict, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'users.db')

def list_user_threads(username: str, db_path: str = DB_PATH) -> List[Dict]:
    """
    列出指定用户的会话线程摘要（按 id 降序）。
    返回字段：id, title, created_at, last_preview, last_at, msg_count
    """
    if not Path(db_path).exists():
        return []
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        SELECT
            t.id,
            t.title,
            t.created_at,
            (SELECT substr(m.content,1,200) FROM messages m WHERE m.thread_id = t.id ORDER BY m.id DESC LIMIT 1) AS last_preview,
            (SELECT m.created_at FROM messages m WHERE m.thread_id = t.id ORDER BY m.id DESC LIMIT 1) AS last_at,
            (SELECT COUNT(*) FROM messages m WHERE m.thread_id = t.id) AS msg_count
        FROM threads t
        WHERE t.username = ?
        ORDER BY t.id DESC
    """, (username,))
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "id": r[0],
            "title": r[1],
            "created_at": r[2],
            "last_preview": r[3],
            "last_at": r[4],
            "msg_count": r[5],
        } for r in rows
    ]

def get_thread_messages(username: str, thread_id: int, db_path: str = DB_PATH) -> Optional[List[Dict]]:
    """
    获取指定用户线程的所有消息（按插入顺序）。
    若线程不存在或不属于用户，返回 None。
    返回字段：id, role, content, created_at
    """
    if not Path(db_path).exists():
        return None
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    # 验证线程属于该用户
    cur.execute("SELECT id FROM threads WHERE id = ? AND username = ?", (thread_id, username))
    if not cur.fetchone():
        conn.close()
        return None
    cur.execute("SELECT id, role, content, created_at FROM messages WHERE thread_id = ? ORDER BY id ASC", (thread_id,))
    rows = cur.fetchall()
    conn.close()
    return [{"id": r[0], "role": r[1], "content": r[2], "created_at": r[3]} for r in rows]

if __name__ == "__main__":
    # 简单 CLI 测试
    import sys
    if len(sys.argv) < 3:
        print("用法:")
        print("  列出用户线程: python src/history.py list <username>")
        print("  查看线程消息: python src/history.py msgs <username> <thread_id>")
        sys.exit(1)

    cmd = sys.argv[1]
    user = sys.argv[2]
    if cmd == "list":
        for t in list_user_threads(user):
            print(f"#{t['id']} {t['title'] or '(无标题)'} ({t['msg_count']} 条) 最后: {t['last_at']}")
            if t['last_preview']:
                print("  预览:", t['last_preview'])
    elif cmd == "msgs" and len(sys.argv) == 4:
        tid = int(sys.argv[3])
        msgs = get_thread_messages(user, tid)
        if msgs is None:
            print("线程不存在或无权限")
        else:
            for m in msgs:
                who = "用户" if m['role'] == 'user' else "助手"
                print(f"[{m['created_at']}] {who}:")
                print(m['content'])
                print("----")
    else:
        print("参数错误")