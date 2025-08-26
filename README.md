# TeacherAgent

#### 介绍
基于个人知识库与检索增强生成机制的导师agent（简称导师agent）

#### 软件架构
软件架构说明

computer-teacher-agent/    # 项目根目录
│
├── data/                  # 存放原始知识库文档（PDF, Word, TXT等）
│   └── raw_documents/     # 例如：算法导论.pdf, python官方文档.txt
│
├── knowledge_base/        # 处理后的知识库和向量数据库存储
│   ├── processed/         # 存放清洗、分割后的文本文件 (.txt)
│   └── chroma_db/         # Chroma向量数据库自动创建的持久化目录
│
├── src/                   # 源代码目录
│   ├── __init__.py
│   ├── main.py           # 应用主入口，启动Flask服务器
│   ├── config.py         # 配置文件（加载环境变量、全局设置）
│   ├── vector_db.py      # 向量数据库操作类（初始化、存储、查询）
│   ├── knowledge_processor.py # 知识库处理模块（读取、分割文档）
│   ├── rag_agent.py      # RAG核心逻辑（检索、构造Prompt、调用LLM）
│   └── routes.py         # Flask路由定义（API端点）
│
├── static/               # Flask静态文件目录 (可选)
│   └── css/
│       └── style.css
│
├── templates/            # Flask Jinja2模板目录 (可选)
│   └── index.html
│
├── tests/                # 单元测试目录
│   └── test_rag_agent.py
│
├── .env                  # 环境变量文件（存储API KEY，勿提交Git）
├── .gitignore           # Git忽略文件规则
├── requirements.txt     # Python项目依赖列表
└── README.md           # 项目说明文档