from flask import Blueprint
from cola.application.service.chatService import chat_service

bp_ask = Blueprint("ask", __name__)

@bp_ask.route('/ask', methods=['POST', 'GET'])
def ask_stream():
    return chat_service.ask()