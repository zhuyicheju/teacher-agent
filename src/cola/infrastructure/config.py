# cola/config.py
import os
from dotenv import load_dotenv


PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
DB_DIR = os.path.join(PROJECT_DIR, 'data', 'users.db')
TEMPLATE_DIR = os.path.join(PROJECT_DIR, 'templates')
STATIC_DIR = os.path.join(PROJECT_DIR, 'static')
VECTOR_DIR = os.path.join(PROJECT_DIR, 'knowledge_base')

load_dotenv(dotenv_path=PROJECT_DIR)  # 只需这一行，自动读取项目根目录的 .env 文件
API_KEY = os.getenv("API_KEY")