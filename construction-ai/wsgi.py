"""Entry point: `python wsgi.py` for local dev, or `gunicorn wsgi:app` in production."""
import os

from dotenv import load_dotenv

load_dotenv()

from buildmate import create_app  # noqa: E402

app = create_app()

if __name__ == "__main__":
    # OAuth providers require http://localhost (not 127.0.0.1) to match registered redirect URIs.
    os.environ.setdefault("AUTHLIB_INSECURE_TRANSPORT", "1")
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", 5000)), debug=True)
