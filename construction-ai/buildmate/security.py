"""Signed tokens, password policy and redirect safety."""
import re
from urllib.parse import urljoin, urlparse

from flask import current_app, request, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer


def _serializer(salt):
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=salt)


def make_token(purpose, payload):
    return _serializer(purpose).dumps(payload)


def read_token(purpose, token, max_age):
    """Return the payload, or None if the token is invalid or expired."""
    try:
        return _serializer(purpose).loads(token, max_age=max_age)
    except (SignatureExpired, BadSignature):
        return None


def external_url(endpoint, **values):
    base = current_app.config.get("BASE_URL")
    if base:
        return base + url_for(endpoint, **values)
    return url_for(endpoint, _external=True, **values)


def password_problems(password):
    problems = []
    if len(password) < 8:
        problems.append("at least 8 characters")
    if not re.search(r"[A-Za-z]", password):
        problems.append("a letter")
    if not re.search(r"\d", password):
        problems.append("a number")
    return problems


def is_safe_next(target):
    if not target:
        return False
    host = urlparse(request.host_url)
    dest = urlparse(urljoin(request.host_url, target))
    return dest.scheme in ("http", "https") and host.netloc == dest.netloc and target.startswith("/")
