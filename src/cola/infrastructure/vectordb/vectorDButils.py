import traceback

from cola.domain.factory.VectorDBFactory import VectorDBFactory
from cola.infrastructure.os.os import delete_directory

def delete_vectors(username, thread_id, vector_ids):
    try:
        vdb = VectorDBFactory.get_instances_withoutcreate(username, thread_id)
        if vector_ids:
            vdb.delete_documents(vector_ids)
    except Exception as e:
        print("管理员删除向量失败：", e, traceback.format_exc())

def delete_vector_dir(username, thread_id):
    # 删除 persist 目录
    try:
        vdb = VectorDBFactory.get_instances_withoutcreate(username=username, thread_id=thread_id)
        persist_dir = getattr(vdb, 'persist_directory', None)
        delete_directory(persist_dir)
    except Exception as e:
        print("管理员移除 persist_directory 失败：", e)
