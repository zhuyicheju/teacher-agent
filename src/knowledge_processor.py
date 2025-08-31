from flask import Blueprint, request, jsonify, session
import os
import re
import sqlite3
from typing import List
from vector_db import VectorDB
from datetime import datetime
from pathlib import Path
from werkzeug.utils import secure_filename
import traceback
import logging

knowledge_processor_app = Blueprint('knowledge_processor', __name__)

# 项目 users.db 路径（与 main.py 保持一致）
DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'users.db'))

# 新增：允许的文件扩展
ALLOWED_EXTENSIONS = {'pdf', 'docx'}

# 新增：简单 logger（写入 data/logs/upload_errors.log）
LOG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'logs'))
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(LOG_DIR, 'upload_errors.log'),
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

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
        # 新增：如果没有 original_filename 列，则添加并将已有 filename 值复制过去（兼容旧数据）
        if 'original_filename' not in cols:
            cur.execute('ALTER TABLE documents ADD COLUMN original_filename TEXT DEFAULT NULL')
            # 将已有 filename 复制到 original_filename（仅针对旧记录）
            try:
                cur.execute("UPDATE documents SET original_filename = filename WHERE original_filename IS NULL")
            except Exception:
                # 忽略更新失败
                pass
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

def allowed_file(filename: str) -> bool:
    if not filename or '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS

@knowledge_processor_app.route('/upload', methods=['POST'])
def upload_file():
    # 必须登录
    user = session.get('user')
    if not user:
        return jsonify({"error": "未登录"}), 401

    if 'file' not in request.files:
        return jsonify({"error": "未发现上传文件"}), 400

    file = request.files['file']
    if not file or file.filename == '':
        return jsonify({"error": "文件名为空"}), 400

    # 保存原始文件名（未经 secure_filename 改写）
    original_filename = file.filename

    # 使用安全文件名并检查扩展
    filename = secure_filename(file.filename)
    if not allowed_file(filename):
        return jsonify({"error": f"不支持的文件类型，仅支持: {', '.join(sorted(ALLOWED_EXTENSIONS))}"}), 400

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
    try:
        os.makedirs(thread_dir, exist_ok=True)
    except Exception as e:
        tb = traceback.format_exc()
        logger.error("创建存储目录失败: %s\n%s", str(e), tb)
        return jsonify({"error": "服务器无法创建存储目录", "detail": str(e)}), 500

    file_path = os.path.join(thread_dir, filename)
    try:
        file.save(file_path)
    except Exception as e:
        tb = traceback.format_exc()
        logger.error("保存上传文件失败: %s\n%s", str(e), tb)
        return jsonify({"error": "保存上传文件失败", "detail": str(e)}), 500

    try:
        processed_segments = process_uploaded_document(file_path)
    except Exception as e:
        tb = traceback.format_exc()
        logger.error("读取或分割文档失败: %s\n%s", str(e), tb)
        return jsonify({"error": "读取或分割文档失败", "detail": str(e)}), 500

    vector_error = None
    stored_ids = []
    doc_id = None
    try:
        # 使用按用户/会话隔离的 VectorDB（传入 username 与 thread_id）
        db = VectorDB(username=user, thread_id=thread_id)
        # metadata 包含 username、source_file、thread_id 与 segment_index
        metadatas = [{"username": user, "source_file": original_filename, "thread_id": thread_id, "segment_index": i+1} for i in range(len(processed_segments))]
        # ids 加入 user/thread 信息以便唯一识别
        if thread_id is not None:
            ids = [f"{user}__thread_{thread_id}__{os.path.splitext(filename)[0]}_seg_{i+1:04d}" for i in range(len(processed_segments))]
        else:
            ids = [f"{user}__{os.path.splitext(filename)[0]}_seg_{i+1:04d}" for i in range(len(processed_segments))]
        stored_ids = db.add_documents(processed_segments, metadatas=metadatas, ids=ids)

        # 在 users.db 中记录 document 与 segments（包含 thread_id），同时保存 original_filename
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        # 适配可能不存在 original_filename 列的旧 DB（ensure_docs_tables 已添加列，但以防）
        try:
            cur.execute('INSERT INTO documents (username, filename, original_filename, stored_at, segment_count, thread_id) VALUES (?, ?, ?, ?, ?, ?)',
                        (user, filename, original_filename, datetime.utcnow().isoformat(), len(processed_segments), thread_id))
        except Exception:
            # 退回到没有 original_filename 列的插入（兼容性）
            cur.execute('INSERT INTO documents (username, filename, stored_at, segment_count, thread_id) VALUES (?, ?, ?, ?, ?)',
                        (user, filename, datetime.utcnow().isoformat(), len(processed_segments), thread_id))
            # 尝试更新 original_filename 列（若存在）
            try:
                doc_id_temp = cur.lastrowid
                cur.execute('UPDATE documents SET original_filename = ? WHERE id = ?', (original_filename, doc_id_temp))
            except Exception:
                pass

        doc_id = cur.lastrowid
        for idx, vid in enumerate(stored_ids, start=1):
            preview = processed_segments[idx-1][:200]
            cur.execute('INSERT INTO document_segments (document_id, segment_index, vector_id, preview) VALUES (?, ?, ?, ?)',
                        (doc_id, idx, vid, preview))
        conn.commit()
        conn.close()

    except Exception as e:
        # 记录完整堆栈到日志，便于排查 VectorDB/Chroma/嵌入相关的问题
        tb = traceback.format_exc()
        logger.error("向量化或写入数据库失败: %s\n%s", str(e), tb)
        vector_error = str(e)

    # 根据是否创建了 documents 记录返回 success 标志与文档信息
    success = doc_id is not None
    document_info = None
    if success:
        # 返回给前端的 filename 字段使用原始文件名（未被 secure_filename 改写）
        document_info = {
            "id": doc_id,
            "username": user,
            "filename": original_filename,
            "stored_at": datetime.utcnow().isoformat(),
            "segment_count": len(processed_segments),
            "thread_id": thread_id
        }

    # 若在向量化阶段出现错误，返回 500 并携带 vector_error（前端可显示给开发人员）
    status_code = 200 if success else 500
    resp = {
        "success": success,
        "message": "上传完成" if success else "上传失败（详见 vector_error 或后端日志）",
        "document": document_info,
        "segments": processed_segments,
        "stored_ids": stored_ids,
        "vector_error": vector_error
    }
    # 开发者可通过设置环境变量 DEV_MODE=1 来在响应中包含更多调试信息（例如日志位置）
    if os.environ.get('DEV_MODE') == '1' and not success:
        resp['_debug_log'] = os.path.join(LOG_DIR, 'upload_errors.log')
    return jsonify(resp), status_code

def process_uploaded_document(file_path: str) -> List[str]:
    content = read_document(file_path)
    if not content or not content.strip():
        raise ValueError("读取的文档内容为空，无法分割")
    return split_document(content)

def list_user_document_titles(username: str, limit: int = 100, thread_id: int = None):
    """
    返回指定用户的文档标题列表（仅标题/文件名、文档 id 与所属 thread）。
    若提供 thread_id 则只返回该会话下的文档（实现会话级知识隔离）。
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # 使用 original_filename 作为展示名（回退到 filename 如果 original_filename 为空）
    if thread_id is None:
        cur.execute('SELECT id, COALESCE(original_filename, filename), thread_id FROM documents WHERE username = ? ORDER BY id DESC LIMIT ?', (username, limit))
    else:
        cur.execute('SELECT id, COALESCE(original_filename, filename), thread_id FROM documents WHERE username = ? AND thread_id = ? ORDER BY id DESC LIMIT ?', (username, thread_id, limit))
    rows = cur.fetchall()
    conn.close()
    return [{'id': r[0], 'title': r[1], 'thread_id': r[2]} for r in rows]

@knowledge_processor_app.route('/knowledge_titles', methods=['GET'])
def knowledge_titles():
    """
    API: /knowledge_titles?thread_id=<id>
    返回当前登录用户已上传知识文档的标题列表（仅文件名作为标题）。
    支持可选的 thread_id 参数用于仅显示该会话下的知识（会话隔离）。
    """
    user = session.get('user')
    if not user:
        return jsonify({"error": "未登录"}), 401

    thread_id = request.args.get('thread_id')
    try:
        thread_id = int(thread_id) if thread_id not in (None, '', 'null') else None
    except Exception:
        thread_id = None

    items = list_user_document_titles(user, thread_id=thread_id)
    return jsonify({'items': items})