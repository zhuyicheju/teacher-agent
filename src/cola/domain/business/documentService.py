from cola.domain.utils.document import read_document, split_document

class DocumentService:
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

    def document_belongs_to_user(doc_id: int, username: str):
        """
        返回 (filename, thread_id) 或 None
        """
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute('SELECT filename, thread_id FROM documents WHERE id = ? AND username = ?', (doc_id, username))
        row = cur.fetchone()
        conn.close()
        if not row:
            return None
        return (row[0], row[1])

    def list_user_documents(username: str, limit: int = 100, thread_id: int = None):
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        if thread_id is None:
            # 未指定 thread_id 时，查询所有文件，返回时使用 original_filename（回退到 filename）
            cur.execute(
                'SELECT id, COALESCE(original_filename, filename) as filename, stored_at, segment_count, thread_id FROM documents WHERE username = ? ORDER BY id DESC LIMIT ?',
                (username, limit))
        else:
            # 指定 thread_id 时，仅查询该会话的文件
            cur.execute(
                'SELECT id, COALESCE(original_filename, filename) as filename, stored_at, segment_count, thread_id FROM documents WHERE username = ? AND thread_id = ? ORDER BY id DESC LIMIT ?',
                (username, thread_id, limit))
        rows = cur.fetchall()
        conn.close()
        return [{'id': r[0], 'filename': r[1], 'stored_at': r[2], 'segment_count': r[3], 'thread_id': r[4]} for r in
                rows]

    def get_document_segments(username: str, document_id: int):
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        # 验证文档属于该用户
        cur.execute('SELECT id FROM documents WHERE id = ? AND username = ?', (document_id, username))
        if not cur.fetchone():
            conn.close()
            return None
        cur.execute(
            'SELECT segment_index, vector_id, preview FROM document_segments WHERE document_id = ? ORDER BY segment_index ASC',
            (document_id,))
        rows = cur.fetchall()
        conn.close()
        return [{'index': r[0], 'vector_id': r[1], 'preview': r[2]} for r in rows]

    def process_uploaded_document(file_path: str) -> List[str]:
        content = read_document(file_path)
        if not content or not content.strip():
            raise ValueError("读取的文档内容为空，无法分割")
        return split_document(content)


document_service = DocumentService()