from flask import Blueprint
from cola.application.service.chatService import chat_service

bp_generate_title = Blueprint("generate_title", __name__)

@bp_generate_title.route('/generate_title', methods=['POST'])
def generate_title_endpoint():
    return chat_service.generate_title()