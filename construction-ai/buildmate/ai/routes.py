from flask import Blueprint, abort, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from .. import render_markdown
from ..extensions import db
from ..forms import SimpleForm
from ..models import Conversation, Message, utcnow
from .providers import active_provider, generate_reply
from .tools import TOOLS, build_prompt, missing_required, title_for

bp = Blueprint("ai", __name__, url_prefix="/ai")

MAX_MESSAGE_CHARS = 12000
MAX_HISTORY = 30


def _own_conversation(conv_id):
    conv = db.session.get(Conversation, conv_id)
    if conv is None or conv.user_id != current_user.id:
        abort(404)
    return conv


def _run(conv):
    history = [{"role": m.role, "content": m.content} for m in conv.messages][-MAX_HISTORY:]
    try:
        text, provider = generate_reply(current_user, conv.tool, history)
    except Exception:  # noqa: BLE001 — surface provider errors to the user without a 500
        current_app.logger.exception("AI provider call failed")
        return None
    msg = Message(conversation=conv, role="assistant", content=text or "(empty response)")
    db.session.add(msg)
    db.session.commit()
    return msg


@bp.route("/")
@login_required
def tools():
    return render_template("ai/tools.html", tools=TOOLS, provider=active_provider())


@bp.route("/tool/<tool_key>", methods=["GET", "POST"])
@login_required
def tool(tool_key):
    if tool_key not in TOOLS:
        abort(404)
    if tool_key == "assistant":
        return redirect(url_for("ai.new_chat"))
    form = SimpleForm()
    if request.method == "POST" and form.validate_on_submit():
        data = {f["name"]: request.form.get(f["name"], "")[:MAX_MESSAGE_CHARS] for f in TOOLS[tool_key]["fields"]}
        missing = missing_required(tool_key, data)
        if missing:
            flash("Please fill in: " + ", ".join(missing), "error")
            return render_template("ai/tool.html", key=tool_key, tool=TOOLS[tool_key], form=form, values=data)
        conv = Conversation(user_id=current_user.id, tool=tool_key, title=title_for(tool_key, data)[:200])
        db.session.add(conv)
        db.session.add(Message(conversation=conv, role="user", content=build_prompt(tool_key, data)))
        db.session.commit()
        if _run(conv) is None:
            flash("The AI service couldn't be reached. Your request was saved — try sending it again.", "error")
        return redirect(url_for("ai.chat", conv_id=conv.id))
    return render_template("ai/tool.html", key=tool_key, tool=TOOLS[tool_key], form=form, values={})


@bp.route("/chat")
@login_required
def new_chat():
    return render_template("ai/chat.html", conv=None, tools=TOOLS, conversations=_recent(), provider=active_provider())


@bp.route("/chat/<int:conv_id>")
@login_required
def chat(conv_id):
    conv = _own_conversation(conv_id)
    return render_template("ai/chat.html", conv=conv, tools=TOOLS, conversations=_recent(), provider=active_provider(), action_form=SimpleForm())


def _recent():
    return (
        Conversation.query.filter_by(user_id=current_user.id)
        .order_by(Conversation.updated_at.desc())
        .limit(40)
        .all()
    )


@bp.route("/api/send", methods=["POST"])
@login_required
def api_send():
    payload = request.get_json(silent=True) or {}
    text = (payload.get("message") or "").strip()
    if not text:
        return jsonify({"error": "Message is empty."}), 400
    if len(text) > MAX_MESSAGE_CHARS:
        return jsonify({"error": f"Message is too long (max {MAX_MESSAGE_CHARS} characters)."}), 400

    conv_id = payload.get("conversation_id")
    if conv_id:
        conv = _own_conversation(int(conv_id))
    else:
        conv = Conversation(user_id=current_user.id, tool="assistant", title=text.splitlines()[0][:80])
        db.session.add(conv)
    db.session.add(Message(conversation=conv, role="user", content=text))
    conv.updated_at = utcnow()
    db.session.commit()

    msg = _run(conv)
    if msg is None:
        return jsonify({"error": "The AI service couldn't be reached. Please try again.", "conversation_id": conv.id}), 502
    return jsonify(
        {
            "conversation_id": conv.id,
            "reply": msg.content,
            "reply_html": str(render_markdown(msg.content)),
            "url": url_for("ai.chat", conv_id=conv.id),
        }
    )


@bp.route("/chat/<int:conv_id>/delete", methods=["POST"])
@login_required
def delete_chat(conv_id):
    if not SimpleForm().validate_on_submit():
        abort(400)
    conv = _own_conversation(conv_id)
    db.session.delete(conv)
    db.session.commit()
    flash("Conversation deleted.", "info")
    return redirect(url_for("ai.new_chat"))


@bp.route("/calculators")
@login_required
def calculators():
    return render_template("ai/calculators.html")
