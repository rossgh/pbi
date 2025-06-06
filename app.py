from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import AzureOpenAI

app = Flask(__name__)
CORS(app)

client = AzureOpenAI(
    api_version="2024-12-01-preview",  # or 2025-01-01-preview if you've been using that
    azure_endpoint="https://airesource0741003294.cognitiveservices.azure.com/",
    api_key="7fbe5a6483c14035a1a99ca22a679327"  # Paste from portal (Key1)
)

@app.route("/", methods=["GET"])
def home():
    return "Azure App is running. Use POST /chat to interact with the model."

@app.route("/chat", methods=["POST"])
def chat():
    try:
        user_input = request.json.get("message", "")
        if not user_input:
            return jsonify({"error": "No message provided"}), 400

        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": user_input}
            ],
            max_tokens=4096,
            temperature=1.0,
            top_p=1.0,
            model="gpt-4o"  # This must match your deployment name exactly
        )

        reply = response.choices[0].message.content
        return jsonify({"response": reply})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)