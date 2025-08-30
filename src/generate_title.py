from flask import Flask, request, jsonify, Response, session
import sqlite3
from datetime import datetime
import traceback
from typing import Optional
from rag_agent import generate_title_sync
from init import DB_PATH

app = Flask(__name__)

def _find_latest_thread_for_user(username: str) -> Optional[int]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT id FROM threads WHERE username = ? ORDER BY id DESC LIMIT 1', (username,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

def _thread_belongs_to_user(thread_id: int, username: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT 1 FROM threads WHERE id = ? AND username = ?', (thread_id, username))
    ok = cur.fetchone() is not None
    conn.close()
    return ok

def _update_thread_title(thread_id: int, title: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('UPDATE threads SET title = ? WHERE id = ?', (title, thread_id))
    conn.commit()
    conn.close()

@app.route('/generate_title', methods=['POST'])
def generate_title_endpoint():
    """
    POST /generate_title
    Body JSON: { "question": "...", "thread_id": optional }
    返回: { "title": "...", "thread_id": 123 }
    会将生成的标题写入 threads 表的 title 字段以便刷新后持久显示。
    """
    if not session.get('user'):
        return jsonify({'error': '未登录'}), 401

    data = request.get_json(silent=True) or request.form or {}
    question = (data.get('question') or '').strip()
    thread_id = data.get('thread_id')

    if not question:
        return jsonify({'error': 'question 不能为空'}), 400

    try:
        if thread_id is not None and str(thread_id).strip() != '':
            try:
                thread_id = int(thread_id)
            except Exception:
                return jsonify({'error': 'thread_id 格式错误'}), 400
            # 校验归属
            if not _thread_belongs_to_user(thread_id, session.get('user')):
                return jsonify({'error': '线程不存在或不属于当前用户'}), 403
        else:
            # 未提供 thread_id，则选择该用户最近的线程
            thread_id = _find_latest_thread_for_user(session.get('user'))
            if thread_id is None:
                return jsonify({'error': '未找到可更新标题的线程'}), 404

        # 生成标题：使用同步接口 generate_title_sync（不使用流式 rag_answer_stream）
        title = generate_title_sync(question, username=session.get('user'), thread_id=thread_id, top_k=1)
        title = (title or '').strip().replace('\n', ' ')

        if title:
            if len(title) > 120:
                title = title[:120].rstrip() + '...'
            # 写入数据库以永久保存
            try:
                _update_thread_title(thread_id, title)
            except Exception as e:
                # 写入失败仍返回生成的标题，但给出警告
                return jsonify({'title': title, 'thread_id': thread_id, 'warning': f'更新数据库失败: {e}'}), 200

            return jsonify({'title': title, 'thread_id': thread_id}), 200
        else:
            return jsonify({'error': '模型未生成标题'}), 500

    except Exception as e:
        tb = traceback.format_exc()
        # 记录到服务器日志以便排查（此处仅返回简短错误）
        print('generate_title error:', e, tb)
        return jsonify({'error': '生成标题失败', 'detail': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)