import os

from cola.domain.factory.Appfactory import AppFactory

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
template_path = os.path.join(base_dir, 'templates')
static_path = os.path.join(base_dir, 'static')

def main():
    # 创建应用实例
    app = AppFactory.create_app()

    # 运行应用
    app.run(debug=True)

if __name__ == '__main__':
    main()