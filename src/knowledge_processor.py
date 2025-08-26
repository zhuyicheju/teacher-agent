from flask import Blueprint, request, jsonify
import os
import re
from typing import List
from vector_db import VectorDB

knowledge_processor_app = Blueprint('knowledge_processor', __name__)

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
    # 延迟导入第三方库，避免在模块导入阶段因缺少依赖导致整个模块加载失败
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
    """
    使用 langchain 的 RecursiveCharacterTextSplitter 对文本进行分块。
    若环境中未安装 langchain，会抛出 ImportError 并给出安装建议。
    """
    try:
        from langchain.text_splitter import RecursiveCharacterTextSplitter
    except ImportError:
        raise ImportError("缺少 langchain，无法分割文本。请运行: python -m pip install langchain")
    
    # 针对中文语料设置分隔符优先级
    separators = ["\n\n", "\n", "。", "！", "？", "；", "，", ",", " "]
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=separators
    )
    # 返回分割后的块列表
    segments = splitter.split_text(content)
    # 去除空白并返回
    return [seg.strip() for seg in segments if seg.strip()]

@knowledge_processor_app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "未发现上传文件"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "文件名为空"}), 400

    raw_documents_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw_documents')
    raw_documents_dir = os.path.abspath(raw_documents_dir)
    os.makedirs(raw_documents_dir, exist_ok=True)
    file_path = os.path.join(raw_documents_dir, file.filename)
    file.save(file_path)

    try:
        # 分割文档
        processed_segments = process_uploaded_document(file_path)
    except Exception as e:
        return jsonify({"error": f"读取或分割文档失败: {e}"}), 500

    # 尝试向量化并存入向量库
    vector_error = None
    stored_ids = []
    try:
        db = VectorDB()  # 使用你已写死的向量模块（ZhipuAI 硬编码）
        # 构造简单元数据
        metadatas = [{"source_file": file.filename, "segment_index": i+1} for i in range(len(processed_segments))]
        ids = [f"{os.path.splitext(file.filename)[0]}_seg_{i+1:04d}" for i in range(len(processed_segments))]
        stored_ids = db.add_documents(processed_segments, metadatas=metadatas, ids=ids)
    except Exception as e:
        vector_error = str(e)

    print("upload debug -> file:", file.filename)
    print("upload debug -> segments:", len(processed_segments))
    print("upload debug -> stored_ids:", stored_ids)
    print("upload debug -> vector_error:", vector_error)

    return jsonify({
        "message": "上传完成",
        "segments": processed_segments,
        "stored_ids": stored_ids,
        "vector_error": vector_error
    }), 200

def process_uploaded_document(file_path: str) -> List[str]:
    content = read_document(file_path)
    # 如果读取为空，抛出异常让上层返回错误给前端
    if not content or not content.strip():
        raise ValueError("读取的文档内容为空，无法分割")
    # 使用已定义的 split_document 进行分块并返回分段列表
    return split_document(content)