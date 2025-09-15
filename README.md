# TeacherAgent

## 项目介绍
TeacherAgent 是一款基于个人知识库与检索增强生成（RAG）机制的导师代理系统，能够帮助用户基于上传的文档（PDF、DOCX等）进行智能问答、文档管理和会话交互，提供精准的知识检索与解答服务。

## 功能介绍
1. **用户认证**：支持用户注册、登录和注销功能，保障用户数据安全
2. **文档管理**：
   - 上传PDF、DOCX格式文档（最大支持10MB）
   - 查看文档列表及分段预览
   - 删除自有文档
3. **会话管理**：
   - 创建和管理会话
   - 基于会话隔离知识文档
4. **智能问答**：
   - 基于上传文档内容进行精准问答
   - 问题分级与优化
   - 流式回答生成
5. **管理员功能**：专用管理员界面，便于系统管理

## 环境要求
- Python 3.12 及以上版本
- 网络连接（用于调用第三方API）

## 依赖环境设置

### 方法1：使用requirements.txt

### 方法2：使用pyproject.toml
```bash
# 创建venv虚拟环境

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate''

# 或者创建conda环境(方法略)

# 安装依赖
pip install .

```

## 配置设置
1. 在项目根目录创建`.env`文件，添加必要的环境变量：
   ```
   API_KEY=你的API密钥
   ```
   > 注意：.env文件包含敏感信息，已加入.gitignore，请勿提交到版本控制系统

## 部署与运行

### 直接运行
```bash
# 激活虚拟环境（同上）

# 运行应用
python src/cola/Application.py
```
### 在pycharm中运行
```bash
打开 Run/Debug Configurations，新建一个 Python 配置:

Name: Run cola.Application

Module name: cola.Application
（这里不要写 Script path，要用 Module name，PyCharm 会自动执行 python -m cola.Application）

Parameters: 

Working directory: 设成项目根目录

Path to .env files: 设成对应.env文件路径

Python interpreter: 选项目对应的虚拟环境解释器
```

应用启动后，默认在本地`http://127.0.0.1:5000`运行，可通过浏览器访问。

## 使用方法

1. **注册与登录**：
   - 访问系统首页，点击注册按钮创建账号
   - 使用注册的账号登录系统

2. **文档上传与管理**：
   - 在首页点击"点击选择或拖放文件至此"区域上传文档
   - 支持PDF和DOCX格式，最大10MB
   - 上传后可在左侧文档列表查看，点击可查看分段预览
   - 可通过"删除"按钮移除不需要的文档

3. **会话与问答**：
   - 点击"新建会话"创建新的会话
   - 在会话窗口输入问题，系统会基于已上传的文档内容进行回答
   - 系统会自动为会话生成标题，并支持查看历史会话

4. **管理员功能**：
   - 使用管理员账号登录
   - 访问`/admin`路径进入管理员界面

## 项目结构
```
teacher-agent/                # 项目根目录
├── data/                     # 数据存储目录
│   └── raw_documents/        # 原始文档存储
├── knowledge_base/           # 知识库目录
│   ├── processed/            # 处理后的文本
│   └── chroma_db/            # 向量数据库
├── src/                      # 源代码目录
│   ├── cola/                 # 核心代码
│   │   ├── application/      # 应用服务
│   │   ├── adapter/          # 适配器层
│   │   ├── domain/           # 领域模型
│   │   └── infrastructure/   # 基础设施
│   └── teacher_agent.egg-info/ # 包信息
├── static/                   # 静态资源
├── templates/                # 网页模板
├── tests/                    # 测试代码
├── .env                      # 环境变量
├── .gitignore                # Git忽略规则
├── pyproject.toml            # 项目配置
├── requirements.txt          # 依赖列表
└── README.md                 # 项目说明
```

## 技术栈
- 后端框架：Flask
- 向量数据库：Chroma
- 文档处理：pdfminer.six、python-docx
- 大模型集成：zhipuai
- 知识检索：langchain