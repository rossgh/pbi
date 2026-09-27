import logging

import markdown as md
import nh3
from flask import Blueprint, Flask, current_app, redirect, render_template, url_for
from flask_login import current_user, login_required
from markupsafe import Markup

from .config import Config
from .extensions import csrf, db, login_manager, oauth

main = Blueprint("main", __name__)

ALLOWED_TAGS = {
    "p", "br", "hr", "h1", "h2", "h3", "h4", "h5", "h6", "strong", "em", "code", "pre", "blockquote",
    "ul", "ol", "li", "table", "thead", "tbody", "tr", "th", "td", "a", "del",
}


def render_markdown(text):
    html = md.markdown(text or "", extensions=["tables", "fenced_code", "sane_lists", "nl2br"])
    return Markup(nh3.clean(html, tags=ALLOWED_TAGS, attributes={"a": {"href"}, "td": {"align"}, "th": {"align"}}))


@main.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    from .ai.tools import TOOLS

    return render_template("index.html", tools=TOOLS)


@main.route("/dashboard")
@login_required
def dashboard():
    if current_user.company_id is None:
        return redirect(url_for("auth.onboarding"))
    from .ai.providers import active_provider
    from .ai.tools import TOOLS
    from .models import Conversation

    recent = (
        Conversation.query.filter_by(user_id=current_user.id).order_by(Conversation.updated_at.desc()).limit(6).all()
    )
    return render_template("dashboard.html", tools=TOOLS, recent=recent, provider=active_provider())


@main.route("/terms")
def terms():
    return render_template("legal.html", title="Terms of Service")


@main.route("/privacy")
def privacy():
    return render_template("legal.html", title="Privacy Policy")


@main.route("/healthz")
def healthz():
    return {"status": "ok"}


def _register_oauth(app):
    oauth.init_app(app)
    if app.config.get("GOOGLE_CLIENT_ID"):
        oauth.register(
            "google",
            client_id=app.config["GOOGLE_CLIENT_ID"],
            client_secret=app.config["GOOGLE_CLIENT_SECRET"],
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"},
        )
    if app.config.get("MICROSOFT_CLIENT_ID"):
        tenant = app.config["MICROSOFT_TENANT"]
        oauth.register(
            "microsoft",
            client_id=app.config["MICROSOFT_CLIENT_ID"],
            client_secret=app.config["MICROSOFT_CLIENT_SECRET"],
            server_metadata_url=f"https://login.microsoftonline.com/{tenant}/v2.0/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"},
        )


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)
    logging.basicConfig(level=logging.INFO)

    if app.config["SECRET_KEY"] == "dev-insecure-change-me" and not app.debug and not app.testing:
        app.logger.warning("SECRET_KEY is not set — using an insecure development key. Set SECRET_KEY in production.")

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    _register_oauth(app)

    from .account.routes import bp as account_bp
    from .ai.routes import bp as ai_bp
    from .auth.routes import bp as auth_bp

    app.register_blueprint(main)
    app.register_blueprint(auth_bp)
    app.register_blueprint(account_bp)
    app.register_blueprint(ai_bp)

    app.jinja_env.filters["markdown"] = render_markdown

    @app.context_processor
    def inject_globals():
        from .auth.routes import enabled_providers

        return {"app_name": current_app.config["APP_NAME"], "oauth_providers": enabled_providers()}

    @app.after_request
    def security_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        return resp

    @app.errorhandler(403)
    @app.errorhandler(404)
    def not_found(err):
        return render_template("error.html", code=err.code, message=err.description), err.code

    with app.app_context():
        from . import models  # noqa: F401 — register tables

        db.create_all()

    return app
