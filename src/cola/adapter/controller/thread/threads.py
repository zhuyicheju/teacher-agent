from flask import Blueprint, session, jsonify, request
from cola.application.service.threadService import thread_service

bp_threads = Blueprint("threads", __name__)

@bp_threads.route('/threads/<int:thread_id>', methods=['DELETE'])
def delete_thread(thread_id):
    return thread_service.delete_thread(thread_id)

@bp_threads.route('/threads', methods=['GET'])
def threads_list():
    return thread_service.threads_list()

@bp_threads.route('/threads', methods=['POST'])
def threads_create():
    return thread_service.create_thread()

@bp_threads.route('/threads/<int:thread_id>/messages', methods=['GET'])
def thread_messages(thread_id):
    return thread_service.thread_messages(thread_id)