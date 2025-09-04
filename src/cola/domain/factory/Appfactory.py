import os

from flask import Flask

class AppFactory:
    "负责创建flask示例"

    _app = None

    @classmethod
    def create_app(cls):
        """创建并配置Flask应用实例"""
        if cls._app is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            template_path = os.path.join(base_dir, 'templates')
            static_path = os.path.join(base_dir, 'static')

            cls._app = Flask(__name__,
                template_folder=template_path,
                static_folder=static_path)

            # 注册蓝图
            from..adapter.controller.admin.admin import bp_admin
            from..adapter.controller.admin.admin_login import bp_admin_login
            from..adapter.controller.auth.login import bp_login
            from..adapter.controller.auth.logout import bp_logout
            from..adapter.controller.chat.ask import bp_ask
            from..adapter.controller.chat.generate_title import bp_generate_title
            from..adapter.controller.document.knowledge_titles import bp_knowledge_titles
            from..adapter.controller.document.my_documents import bp_my_documents
            from..adapter.controller.document.upload import bp_upload
            from..adapter.controller.thread.threads import bp_threads
            from..adapter.controller.index import bp_index

            cls._app.register_blueprint(bp_admin)
            cls._app.register_blueprint(bp_admin_login)
            cls._app.register_blueprint(bp_login)
            cls._app.register_blueprint(bp_logout)
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
