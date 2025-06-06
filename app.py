from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import AzureOpenAI
import os

app = Flask(__name__)
CORS(app)  # Enable CORS for all domains

# Azure OpenAI client configuration
client = AzureOpenAI(
    api_version="2025-01-01-preview",
    azure_endpoint="https://airesource0741003294.cognitiveservices.azure.com/",
    api_key=os.environ.get("AZURE_OPENAI_KEY", "your-fallback-api-key-here")  # optional fallback
)

# Root route to confirm app is running
@app.route("/", methods=["GET"])
def home():
    return "Azure App is running. Use POST /chat to interact with the model."

# Chat endpoint to interact with Azure OpenAI
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
            model="gpt-4o-cp-studio"
        )

        reply = response.choices[0].message.content
        return jsonify({"response": reply})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)