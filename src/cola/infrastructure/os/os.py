import shutil
import traceback

from flask import jsonify

import os

class osUtils:
    def delete_directory(dir):
        if dir and os.path.isdir(dir):
            shutil.rmtree(dir, ignore_errors=True)

    def get_raw_dir(username, thread_id):
        raw_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '..', 'data', 'raw_documents', username,
                         f"thread_{thread_id}"))
        return raw_dir

    def get_raw_files(owner, doc_thread, filename):
        raw_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '..', 'data', 'raw_documents', owner, f"thread_{doc_thread}",
                         filename))
        return raw_path

    def delete_files(filepath):
        if os.path.exists(filepath):
            os.remove(filepath)

    def delete_document(self, username, thread_id, base_dir):
        try:
            raw_dir = os.path.abspath(
                os.path.join(base_dir, 'data', 'raw_documents', username, f"thread_{thread_id}"))
            if os.path.isdir(raw_dir):
                shutil.rmtree(raw_dir, ignore_errors=True)
        except Exception as e:
            print("移除 raw_documents 失败：", e)

    def upload_document(self, username, thread_id, file, filename):
        # 修改：按用户和会话分层存储文件
        raw_documents_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw_documents')
        user_dir = os.path.join(raw_documents_dir, username)
        thread_dir = os.path.join(user_dir, f"thread_{thread_id}" if thread_id else "no_thread")
        try:
            os.makedirs(thread_dir, exist_ok=True)
        except Exception as e:
            tb = traceback.format_exc()
            print("创建存储目录失败: %s\n%s", str(e), tb)
            return jsonify({"error": "服务器无法创建存储目录", "detail": str(e)}), 500

        file_path = os.path.join(thread_dir, filename)
        try:
            file.save(file_path)
        except Exception as e:
            tb = traceback.format_exc()
            print("保存上传文件失败: %s\n%s", str(e), tb)
            return jsonify({"error": "保存上传文件失败", "detail": str(e)}), 500

        return file_path

os_utils = osUtils()