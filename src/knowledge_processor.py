from flask import Blueprint, request, jsonify, session
import os
import re
import sqlite3
from typing import List
from vector_db import VectorDB
from datetime import datetime
from pathlib import Path

knowledge_processor_app = Blueprint('knowledge_processor', __name__)

# 项目 users.db 路径（与 main.py 保持一致）
DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'users.db'))

def ensure_docs_tables():
    Path(os.path.dirname(DB_PATH)).mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            filename TEXT NOT NULL,
            stored_at TEXT NOT NULL,
            segment_count INTEGER NOT NULL,
            thread_id INTEGER DEFAULT NULL
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS document_segments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            segment_index INTEGER NOT NULL,
            vector_id TEXT NOT NULL,
            preview TEXT,
            FOREIGN KEY(document_id) REFERENCES documents(id)
        )
    ''')
    # 如果已存在旧表但没有 thread_id 列，尝试添加该列（兼容已有 DB）
    try:
        cur.execute("PRAGMA table_info(documents)")
        cols = [r[1] for r in cur.fetchall()]
        if 'thread_id' not in cols:
            cur.execute('ALTER TABLE documents ADD COLUMN thread_id INTEGER DEFAULT NULL')
    except Exception:
        # 忽略无法添加的异常（老 SQLite 可能不支持或已添加）
        pass

    conn.commit()
    conn.close()

ensure_docs_tables()

@knowledge_processor_app.errorhandler(404)
def handle_404(e):
    return jsonify({"error": "资源未找到"}), 404

@knowledge_processor_app.errorhandler(Exception)
def handle_exception(e):
    response = {
        "error": str(e)
    }
    return jsonify(response), 500

def read_document(file_path: str) -> str:
    if file_path.endswith('.pdf'):
        try:
            from pdfminer.high_level import extract_text
        except ImportError:
            raise ImportError("缺少 pdfminer.six，无法读取 PDF。请运行: python -m pip install pdfminer.six")
        return extract_text(file_path)
    elif file_path.endswith('.docx'):
        try:
            from docx import Document
        except ImportError:
            raise ImportError("缺少 python-docx，无法读取 DOCX。请运行: python -m pip install python-docx")
        doc = Document(file_path)
        return '\n'.join([paragraph.text for paragraph in doc.paragraphs])
    else:
        raise ValueError("Unsupported file format. Only PDF and Word files are supported.")

def split_document(content: str) -> List[str]:
    try:
        from langchain.text_splitter import RecursiveCharacterTextSplitter
    except ImportError:
        raise ImportError("缺少 langchain，无法分割文本。请运行: python -m pip install langchain")
    separators = ["\n\n", "\n", "。", "！", "？", "；", "，", ",", " "]
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=separators
    )
    segments = splitter.split_text(content)
    return [seg.strip() for seg in segments if seg.strip()]

@knowledge_processor_app.route('/upload', methods=['POST'])
def upload_file():
    # 必须登录
    user = session.get('user')
    if not user:
        return jsonify({"error": "未登录"}), 401

    if 'file' not in request.files:
        return jsonify({"error": "未发现上传文件"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "文件名为空"}), 400

    # 支持可选的 thread_id（表单字段或查询字符串）
    thread_id = request.form.get('thread_id') or request.args.get('thread_id')
    try:
        thread_id = int(thread_id) if thread_id not in (None, '', 'null') else None
    except Exception:
        thread_id = None

    # 修改：按用户和会话分层存储文件
    raw_documents_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw_documents')
    user_dir = os.path.join(raw_documents_dir, user)
    thread_dir = os.path.join(user_dir, f"thread_{thread_id}" if thread_id else "no_thread")
    os.makedirs(thread_dir, exist_ok=True)
    file_path = os.path.join(thread_dir, file.filename)
    file.save(file_path)

    try:
        processed_segments = process_uploaded_document(file_path)
    except Exception as e:
        return jsonify({"error": f"读取或分割文档失败: {e}"}), 500

    vector_error = None
    stored_ids = []
    try:
        # 使用按用户/会话隔离的 VectorDB（传入 username 与 thread_id）
        db = VectorDB(username=user, thread_id=thread_id)
        # metadata 包含 username、source_file、thread_id 与 segment_index
        metadatas = [{"username": user, "source_file": file.filename, "thread_id": thread_id, "segment_index": i+1} for i in range(len(processed_segments))]
        # ids 加入 user/thread 信息以便唯一识别
        if thread_id is not None:
            ids = [f"{user}__thread_{thread_id}__{os.path.splitext(file.filename)[0]}_seg_{i+1:04d}" for i in range(len(processed_segments))]
        else:
            ids = [f"{user}__{os.path.splitext(file.filename)[0]}_seg_{i+1:04d}" for i in range(len(processed_segments))]
        stored_ids = db.add_documents(processed_segments, metadatas=metadatas, ids=ids)

        # 在 users.db 中记录 document 与 segments（包含 thread_id）
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute('INSERT INTO documents (username, filename, stored_at, segment_count, thread_id) VALUES (?, ?, ?, ?, ?)',
                    (user, file.filename, datetime.utcnow().isoformat(), len(processed_segments), thread_id))
        doc_id = cur.lastrowid
        for idx, vid in enumerate(stored_ids, start=1):
            preview = processed_segments[idx-1][:200]
            cur.execute('INSERT INTO document_segments (document_id, segment_index, vector_id, preview) VALUES (?, ?, ?, ?)',
                        (doc_id, idx, vid, preview))
        conn.commit()
        conn.close()

    except Exception as e:
        vector_error = str(e)

    return jsonify({
        "message": "上传完成",
        "segments": processed_segments,
        "stored_ids": stored_ids,
        "vector_error": vector_error
    }), 200

def process_uploaded_document(file_path: str) -> List[str]:
    content = read_document(file_path)
    if not content or not content.strip():
        raise ValueError("读取的文档内容为空，无法分割")
    return split_document(content)