@knowledge_processor_app.errorhandler(404)
def handle_404(e):
    return jsonify({"error": "资源未找到"}), 404

@knowledge_processor_app.errorhandler(Exception)
def handle_exception(e):
    response = {
        "error": str(e)
    }
    return jsonify(response), 500