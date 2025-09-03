from flask import Blueprint, session, jsonify, request
from cola.application.service.documentService import document_service

bp_knowledge_titles = Blueprint("knowledge_titles", __name__)

@bp_knowledge_titles.route('/knowledge_titles', methods=['GET'])
def knowledge_titles():
    return document_service.knowledge_titles()