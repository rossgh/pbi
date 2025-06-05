from flask import Flask, request, jsonify
from openai import AzureOpenAI

app = Flask(__name__)

client = AzureOpenAI(
    api_version="2025-01-01-preview",
    azure_endpoint="https://airesource0741003294.cognitiveservices.azure.com/",
    api_key="7fbe5a6483c14035a1a99ca22a679327"
)

@app.route("/chat", methods=["POST"])
def chat():
    user_input = request.json.get("message", "")
    response = client.chat.completions.create(
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": user_input}
        ],
        max_tokens=4096,
        temperature=1.0,
        top_p=1.0,
        model="gpt-4o-cp-studio"
    )
    return jsonify({"response": response.choices[0].message.content})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)