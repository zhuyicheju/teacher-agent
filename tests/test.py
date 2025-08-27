from zhipuai import ZhipuAI
import os

client = ZhipuAI(api_key="98ed0ed5a81f4a958432644de29cb547.LLhUp4oWijSoizYc") # 填写您自己的APIKey
response = client.chat.completions.create(
    model="glm-4-0520",  # 填写需要调用的模型编码
    messages=[
        {"role": "user", "content": "作为一名营销专家，请为我的产品创作一个吸引人的slogan"},
    ],
    stream=True
)
print(response)

raw_documents_dir = os.path.join('data', 'raw_documents')
print(raw_documents_dir)