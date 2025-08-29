from flask import Flask, request, jsonify, Response
from zhipuai import ZhipuAI

app = Flask(__name__)


def generate_title(question):
    client = ZhipuAI(api_key="98ed0ed5a81f4a958432644de29cb547.LLhUp4oWijSoizYc")
    prompt = (
        f"根据以下问题生成一个简短的标题：\n\n问题：{question}\n\n标题："
    )
    # 模拟大模型调用
    response = client.chat.completions.create(
        model="glm-4-0520",
        messages=[{"role": "user", "content": prompt}],
        stream=True
    )
    try:
        for chunk in response:
            if hasattr(chunk, 'choices') and chunk.choices:
                delta = chunk.choices[0].delta
                if hasattr(delta, 'content') and delta.content:
                    yield delta.content
    except Exception as e:
        yield f"[ERROR]{str(e)}"

@app.route('/generate_title', methods=['POST'])
def generate_title_endpoint():
    try:
        # 获取请求中的问题
        data = request.json
        question = data.get('question', '').strip()

        if not question:
            return jsonify({"error": "问题不能为空"}), 400

        # 调用生成标题函数
        title_chunks = generate_title(question)
        title = ''.join(title_chunks)

        # 检查生成结果
        if "[ERROR]" in title or not title.strip():
            return jsonify({"error": "生成标题失败"}), 500

        return jsonify({"title": title.strip()})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)