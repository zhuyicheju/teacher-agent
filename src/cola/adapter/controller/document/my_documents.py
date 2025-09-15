from flask import Blueprint, session, jsonify, request
from cola.application.service.documentService import document_service

bp_my_documents = Blueprint("my_documents", __name__)

@bp_my_documents.route('/my_documents/<int:doc_id>', methods=['DELETE'])
def delete_document(doc_id):
    return document_service.delete_document(doc_id)

@bp_my_documents.route('/my_documents', methods=['GET'])
def my_documents():
    return document_service.my_documents()

@bp_my_documents.route('/my_documents/<int:doc_id>/segments', methods=['GET'])
def my_document_segments(doc_id):
    return document_service.my_document_segments(doc_id)

@bp_my_documents.route('/my_documents/<int:doc_id>', methods=['DELETE'])
def delete_my_document(doc_id):
    return document_service.delete_my_document(doc_id)