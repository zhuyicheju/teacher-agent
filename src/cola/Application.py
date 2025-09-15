import os

from cola.domain.factory.Appfactory import AppFactory
from cola.infrastructure import config
from cola.infrastructure.externalServer.zhipuClient import ZhipuClient


def main():
    ZhipuClient(config.API_KEY)

    # 创建应用实例
    app = AppFactory.create_app()

    # 运行应用
    app.run(debug=True)

if __name__ == '__main__':
    main()