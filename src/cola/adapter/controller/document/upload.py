from flask import Blueprint, session, jsonify, request
from cola.application.service.documentService import document_service

bp_upload = Blueprint("upload", __name__)


@bp_upload.route('/upload', methods=['POST'])
def upload_file():
    return document_service.upload_file()