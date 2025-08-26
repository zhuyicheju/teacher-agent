import os
from flask import Flask, request, jsonify, render_template, Response
from zhipuai import ZhipuAI
import json
from knowledge_processor import knowledge_processor_app

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
template_path = os.path.join(base_dir, 'templates')
static_path = os.path.join(base_dir, 'static')

app = Flask(__name__, 
            template_folder=template_path,
            static_folder=static_path)

# 注册 knowledge_processor 的 Blueprint
app.register_blueprint(knowledge_processor_app)

client = ZhipuAI(api_key="98ed0ed5a81f4a958432644de29cb547.LLhUp4oWijSoizYc")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/ask', methods=['POST', 'GET'])
def ask_stream():
    try:
        # 根据请求方法获取问题
        if request.method == 'POST':
            data = request.get_json()
            question = data.get('question', '')
        else:  # GET方法
            question = request.args.get('question', '')
        
        if not question:
            return jsonify({'error': '问题不能为空'}), 400

        # 调用 ZhipuAI 的流式接口
        response = client.chat.completions.create(
            model="glm-4-0520",
            messages=[
                {"role": "user", "content": question},
            ],
            stream=True
        )

        def generate():
            try:
                for chunk in response:
                    if hasattr(chunk, 'choices') and chunk.choices:
                        delta = chunk.choices[0].delta
                        if hasattr(delta, 'content') and delta.content:
                            # 发送JSON格式的数据
                            yield f"data: {json.dumps({'content': delta.content})}\n\n"
                # 发送结束信号
                yield "data: [DONE]\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                yield "data: [DONE]\n\n"

        return Response(generate(), mimetype='text/event-stream')
        
    except Exception as e:
        print("错误信息:", e)
        return jsonify({'error': '服务器内部错误，请稍后再试！'}), 500

if __name__ == '__main__':
    app.run(debug=True)