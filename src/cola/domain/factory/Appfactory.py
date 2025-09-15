import os

from flask import Flask

from cola.infrastructure import config


class AppFactory:
    "负责创建flask示例"

    _app = None

    @classmethod
    def create_app(cls):
        """创建并配置Flask应用实例"""
        if cls._app is None:

            cls._app = Flask(__name__,
                template_folder=config.TEMPLATE_DIR,
                static_folder=config.STATIC_DIR)

            from cola.adapter.controller.admin.admin_login import bp_admin_login
            from cola.adapter.controller.admin.admin import bp_admin
            from cola.adapter.controller.auth.login import bp_login
            from cola.adapter.controller.auth.logout import bp_logout
            from cola.adapter.controller.auth.register import bp_register
            from cola.adapter.controller.chat.ask import bp_ask
            from cola.adapter.controller.chat.generate_title import bp_generate_title
            from cola.adapter.controller.document.my_documents import bp_my_documents
            from cola.adapter.controller.document.upload import bp_upload
            from cola.adapter.controller.document.knowledge_titles import bp_knowledge_titles
            from cola.adapter.controller.thread.threads import bp_threads
            from cola.adapter.controller.index import bp_index

            cls._app.register_blueprint(bp_admin)
            cls._app.register_blueprint(bp_admin_login)
            cls._app.register_blueprint(bp_login)
            cls._app.register_blueprint(bp_logout)
            cls._app.register_blueprint(bp_register)
            cls._app.register_blueprint(bp_ask)
            cls._app.register_blueprint(bp_generate_title)
            cls._app.register_blueprint(bp_knowledge_titles)
            cls._app.register_blueprint(bp_my_documents)
            cls._app.register_blueprint(bp_upload)
            cls._app.register_blueprint(bp_threads)
            cls._app.register_blueprint(bp_index)
        return cls._app

    @classmethod
    def get_app(cls):
        """获取已创建的Flask应用实例"""
        if cls._app is None:
            raise RuntimeError("App not created yet. Call create_app() first.")
        return cls._app
