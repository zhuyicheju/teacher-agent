# cola/config.py
import os
from dotenv import load_dotenv

# 加载 .env 文件（如果存在）
load_dotenv()  # 只需这一行，自动读取项目根目录的 .env 文件

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
DB_DIR = os.path.join(PROJECT_DIR, 'data', 'users.db')
TEMPLATE_DIR = os.path.join(PROJECT_DIR, 'templates')
STATIC_DIR = os.path.join(PROJECT_DIR, 'static')
VECTOR_DIR = os.path.join(PROJECT_DIR, 'knowledge_base')

API_KEY = "98ed0ed5a81f4a958432644de29cb547"
