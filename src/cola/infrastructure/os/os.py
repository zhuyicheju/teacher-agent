import shutil

import os


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