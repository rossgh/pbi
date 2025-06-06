from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from openai import AzureOpenAI
import requests

app = Flask(__name__)
CORS(app)

# Azure OpenAI setup
client = AzureOpenAI(
    api_version="2024-12-01-preview",
    azure_endpoint="https://airesource0741003294.cognitiveservices.azure.com/",
    api_key="7fbe5a6483c14035a1a99ca22a679327"
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
            max_tokens=2048,
            temperature=1.0,
            top_p=1.0,
            model="gpt-4o"
        )

        reply = response.choices[0].message.content
        return jsonify({"response": reply})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/speak", methods=["POST"])
def speak():
    try:
        text = request.data.decode("utf-8")
        voice = request.args.get("voice", "en-US-AndrewMultilingualNeural")

        tts_url = "https://eastus2.tts.speech.microsoft.com/cognitiveservices/v1"
        headers = {
            "Ocp-Apim-Subscription-Key": "CvfyBJcFIkwFoTa7OS23Rcbmp8s1Z8kuunMmoff7YC3GTKHo4MzGJQQJ99BFACHYHv6XJ3w3AAAYACOGIfBa",
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "audio-24khz-48kbitrate-mono-mp3"
        }

        response = requests.post(tts_url, headers=headers, data=text.encode('utf-8'))
        response.raise_for_status()
        return Response(response.content, mimetype='audio/mpeg')

    except Exception as e:
        print("❌ TTS error:", str(e))
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
