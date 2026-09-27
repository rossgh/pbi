import os
from datetime import timedelta


def _bool(name, default=False):
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    APP_NAME = os.environ.get("APP_NAME", "BuildMate AI")
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-insecure-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///buildmate.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Base URL used in emailed links (e.g. https://app.example.com). Falls back to request host.
    BASE_URL = os.environ.get("BASE_URL", "").rstrip("/")

    # When true, emails are not sent but their links are shown on screen and logged.
    DEV_SHOW_EMAIL_LINKS = _bool("DEV_SHOW_EMAIL_LINKS", True)

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _bool("SESSION_COOKIE_SECURE", False)
    REMEMBER_COOKIE_DURATION = timedelta(days=30)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SECURE = _bool("SESSION_COOKIE_SECURE", False)
    WTF_CSRF_TIME_LIMIT = None

    # Token lifetimes (seconds)
    VERIFY_TOKEN_MAX_AGE = 60 * 60 * 48
    RESET_TOKEN_MAX_AGE = 60 * 60
    INVITE_TOKEN_MAX_AGE = 60 * 60 * 24 * 7

    # Login lockout
    MAX_FAILED_LOGINS = int(os.environ.get("MAX_FAILED_LOGINS", 5))
    LOCKOUT_MINUTES = int(os.environ.get("LOCKOUT_MINUTES", 15))

    # SMTP
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_USE_TLS = _bool("MAIL_USE_TLS", True)
    MAIL_FROM = os.environ.get("MAIL_FROM", "BuildMate AI <no-reply@buildmate.local>")

    # OAuth providers — a provider's button only shows when its client id/secret are set.
    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    MICROSOFT_CLIENT_ID = os.environ.get("MICROSOFT_CLIENT_ID", "")
    MICROSOFT_CLIENT_SECRET = os.environ.get("MICROSOFT_CLIENT_SECRET", "")
    MICROSOFT_TENANT = os.environ.get("MICROSOFT_TENANT", "common")

    # AI providers — auto-detected from whichever keys are set; "demo" works with no keys.
    AI_PROVIDER = os.environ.get("AI_PROVIDER", "").lower()
    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-5-5")
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
    OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o")
    AZURE_OPENAI_API_KEY = os.environ.get("AZURE_OPENAI_API_KEY", "")
    AZURE_OPENAI_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
    AZURE_OPENAI_DEPLOYMENT = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    AZURE_OPENAI_API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
    AI_MAX_TOKENS = int(os.environ.get("AI_MAX_TOKENS", 2048))


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    DEV_SHOW_EMAIL_LINKS = True
    AI_PROVIDER = "demo"
    GOOGLE_CLIENT_ID = "test-google"
    GOOGLE_CLIENT_SECRET = "test-google-secret"
    MICROSOFT_CLIENT_ID = "test-ms"
    MICROSOFT_CLIENT_SECRET = "test-ms-secret"
