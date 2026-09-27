import re

import pytest

from buildmate import create_app
from buildmate.auth import routes as auth_routes
from buildmate.config import TestConfig
from buildmate.extensions import db
from buildmate.models import Company, Conversation, Invite, OAuthAccount, User


@pytest.fixture
def app():
    app = create_app(TestConfig)
    yield app
    with app.app_context():
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def register(client, email="pm@acme.com", password="Build1234", company="Acme Builders", name="Pat Morgan"):
    return client.post(
        "/auth/register",
        data={
            "full_name": name,
            "email": email,
            "company_name": company,
            "trade": "Project Manager",
            "password": password,
            "confirm": password,
            "accept_terms": "y",
        },
        follow_redirects=True,
    )


def login(client, email="pm@acme.com", password="Build1234"):
    return client.post("/auth/login", data={"email": email, "password": password}, follow_redirects=True)


def dev_link(resp, path_prefix):
    m = re.search(r'href="(?:http://localhost)?(' + re.escape(path_prefix) + r'[^"]+)"', resp.get_data(as_text=True))
    assert m, f"no dev link for {path_prefix}"
    return m.group(1)


def get_user(app, email="pm@acme.com"):
    """Return the user with its company loaded, so attributes work outside the app context."""
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        if user is not None:
            _ = user.company
            db.session.expunge_all()
        return user


# --- registration, login, logout ------------------------------------------

def test_register_creates_company_owner_and_logs_in(client, app):
    resp = register(client)
    assert resp.status_code == 200
    assert b"Good to see you, Pat" in resp.data
    user = get_user(app)
    assert user.role == "owner"
    assert user.company.name == "Acme Builders"
    assert not user.email_verified


def test_register_requires_company_and_strong_password(client, app):
    resp = register(client, company="")
    assert b"Company name is required" in resp.data
    resp = register(client, password="short")
    assert b"Password needs" in resp.data
    assert get_user(app) is None


def test_duplicate_registration_rejected(client, app):
    register(client)
    client.post("/auth/logout")
    resp = register(client, name="Someone Else")
    assert b"already exists" in resp.data


def test_login_logout_and_bad_password(client):
    register(client)
    client.post("/auth/logout")
    assert b"Incorrect email or password" in login(client, password="wrong1234").data
    assert b"Good to see you" in login(client).data
    client.post("/auth/logout")
    assert client.get("/dashboard").status_code == 302


def test_lockout_after_repeated_failures(client, app):
    register(client)
    client.post("/auth/logout")
    for _ in range(app.config["MAX_FAILED_LOGINS"]):
        login(client, password="nope12345")
    resp = login(client)  # correct password, but locked
    assert b"Too many failed attempts" in resp.data


def test_open_redirect_blocked(client):
    register(client)
    client.post("/auth/logout")
    client.get("/auth/login?next=https://evil.example.com/")
    resp = client.post("/auth/login", data={"email": "pm@acme.com", "password": "Build1234"})
    assert resp.headers["Location"].endswith("/dashboard")


# --- email verification & password reset -----------------------------------

def test_email_verification_link(client, app):
    resp = register(client)
    link = dev_link(resp, "/auth/verify/")
    client.get(link, follow_redirects=True)
    assert get_user(app).email_verified


def test_password_reset_flow_is_single_use_and_signs_out_everywhere(client, app):
    register(client)
    other = app.test_client()
    login(other)
    client.post("/auth/logout")

    resp = client.post("/auth/forgot", data={"email": "pm@acme.com"}, follow_redirects=True)
    assert b"If an account exists" in resp.data
    link = dev_link(resp, "/auth/reset/")
    resp = client.post(link, data={"password": "NewPass999", "confirm": "NewPass999"}, follow_redirects=True)
    assert b"Password updated" in resp.data

    assert b"Good to see you" in login(client, password="NewPass999").data
    # Old session on another device is invalidated
    assert other.get("/dashboard").status_code == 302
    # Link can't be reused
    resp = client.post(link, data={"password": "Another999", "confirm": "Another999"}, follow_redirects=True)
    assert b"invalid, expired, or already used" in resp.data


def test_forgot_password_does_not_reveal_accounts(client):
    resp = client.post("/auth/forgot", data={"email": "nobody@nowhere.com"}, follow_redirects=True)
    assert b"If an account exists" in resp.data
    assert b"/auth/reset/" not in resp.data


# --- profile & security -------------------------------------------------------

def test_profile_update(client, app):
    register(client)
    resp = client.post(
        "/account/profile",
        data={"full_name": "Pat M.", "job_title": "Senior PM", "trade": "Estimator", "phone": "555", "units": "metric", "submit": "1"},
        follow_redirects=True,
    )
    assert b"Profile saved" in resp.data
    user = get_user(app)
    assert (user.full_name, user.job_title, user.units) == ("Pat M.", "Senior PM", "metric")


def test_change_email_requires_confirmation(client, app):
    register(client)
    resp = client.post(
        "/account/email", data={"email-new_email": "new@acme.com", "email-password": "Build1234"}, follow_redirects=True
    )
    assert get_user(app).pending_email == "new@acme.com"
    client.get(dev_link(resp, "/auth/verify/"), follow_redirects=True)
    assert get_user(app, "new@acme.com") is not None


def test_change_password(client):
    register(client)
    resp = client.post(
        "/account/security",
        data={"pw-current_password": "Build1234", "pw-password": "Changed123", "pw-confirm": "Changed123", "pw-submit": "1"},
        follow_redirects=True,
    )
    assert b"Password updated" in resp.data
    client.post("/auth/logout")
    assert b"Good to see you" in login(client, password="Changed123").data


def test_signout_everywhere(client):
    register(client)
    client.post("/account/signout-everywhere", follow_redirects=True)
    assert client.get("/dashboard").status_code == 302


def test_delete_account(client, app):
    register(client)
    resp = client.post("/account/delete", data={"del-confirm_text": "DELETE", "del-password": "Build1234"}, follow_redirects=True)
    assert b"deleted" in resp.data
    with app.app_context():
        assert User.query.count() == 0
        assert Company.query.count() == 0


# --- company & team -----------------------------------------------------------

def test_invite_and_join_team(client, app):
    register(client)
    resp = client.post("/account/team", data={"email": "super@acme.com", "role": "admin"}, follow_redirects=True)
    link = dev_link(resp, "/auth/invite/")
    client.post("/auth/logout")

    invitee = app.test_client()
    resp = invitee.get(link, follow_redirects=True)
    assert b"Create your account to join Acme Builders" in resp.data
    register(invitee, email="super@acme.com", company="", name="Sam Super")
    user = get_user(app, "super@acme.com")
    assert user.company.name == "Acme Builders"
    assert user.role == "admin"
    with app.app_context():
        assert Invite.query.first().accepted_at is not None


def test_owner_cannot_delete_with_members_and_can_transfer(client, app):
    register(client)
    with app.app_context():
        owner = User.query.first()
        member = User(email="crew@acme.com", full_name="Crew", company_id=owner.company_id, role="member")
        member.set_password("Crew12345")
        db.session.add(member)
        db.session.commit()
        member_id = member.id
    resp = client.post("/account/delete", data={"del-confirm_text": "DELETE", "del-password": "Build1234"}, follow_redirects=True)
    assert b"Transfer company ownership" in resp.data
    client.post(f"/account/team/{member_id}/transfer", follow_redirects=True)
    assert get_user(app, "crew@acme.com").role == "owner"
    assert get_user(app).role == "admin"


def test_member_cannot_manage_team(client, app):
    register(client)
    with app.app_context():
        owner = User.query.first()
        m = User(email="crew@acme.com", full_name="Crew", company_id=owner.company_id, role="member")
        m.set_password("Crew12345")
        db.session.add(m)
        db.session.commit()
        owner_id = owner.id
    client.post("/auth/logout")
    login(client, "crew@acme.com", "Crew12345")
    assert client.post(f"/account/team/{owner_id}/remove").status_code == 403
    assert client.post("/account/team", data={"email": "x@y.com", "role": "admin"}).status_code == 403


# --- OAuth ------------------------------------------------------------------

def fake_profile(monkeypatch, **profile):
    monkeypatch.setattr(auth_routes, "fetch_oauth_profile", lambda provider: profile)


def test_google_signup_goes_to_onboarding(client, app, monkeypatch):
    fake_profile(monkeypatch, sub="g-1", email="new@gmail.com", email_verified=True, name="Gina Gee")
    resp = client.get("/auth/oauth/google/callback")
    assert resp.headers["Location"].endswith("/auth/onboarding")
    resp = client.post("/auth/onboarding", data={"company_name": "Gee Construction", "industry_focus": "Residential"}, follow_redirects=True)
    assert b"Gee Construction is set up" in resp.data
    user = get_user(app, "new@gmail.com")
    assert user.email_verified and not user.has_password and user.role == "owner"


def test_google_links_existing_verified_email(client, app, monkeypatch):
    register(client)
    client.post("/auth/logout")
    fake_profile(monkeypatch, sub="g-2", email="pm@acme.com", email_verified=True, name="Pat")
    resp = client.get("/auth/oauth/google/callback", follow_redirects=True)
    assert b"Good to see you" in resp.data
    with app.app_context():
        assert OAuthAccount.query.filter_by(provider="google").count() == 1


def test_microsoft_does_not_auto_link_unverified_email(client, app, monkeypatch):
    register(client)
    client.post("/auth/logout")
    fake_profile(monkeypatch, sub="ms-1", email="pm@acme.com", email_verified=False, name="Pat")
    resp = client.get("/auth/oauth/microsoft/callback", follow_redirects=True)
    assert b"already exists" in resp.data
    with app.app_context():
        assert OAuthAccount.query.count() == 0


def test_link_and_unlink_provider_from_security(client, app, monkeypatch):
    register(client)
    client.get("/auth/oauth/microsoft", follow_redirects=False)  # sets linking flag (redirects to provider)
    fake_profile(monkeypatch, sub="ms-2", email="pat@outlook.com", email_verified=False, name="Pat")
    with client.session_transaction() as s:
        s["oauth_link"] = True
    resp = client.get("/auth/oauth/microsoft/callback", follow_redirects=True)
    assert b"Microsoft connected" in resp.data
    resp = client.post("/account/unlink/microsoft", follow_redirects=True)
    assert b"Microsoft disconnected" in resp.data


def test_cannot_unlink_only_login_method(client, app, monkeypatch):
    fake_profile(monkeypatch, sub="g-3", email="solo@gmail.com", email_verified=True, name="Solo")
    client.get("/auth/oauth/google/callback")
    resp = client.post("/account/unlink/google", follow_redirects=True)
    assert b"Set a password first" in resp.data


# --- AI -------------------------------------------------------------------------

def test_ai_tool_generates_demo_draft_and_chat_continues(client, app):
    register(client)
    resp = client.post(
        "/ai/tool/change_order",
        data={"project": "Riverside Clinic", "change": "Owner added 3 outlets", "labor": "10 x 80", "materials": "300", "markup": "10"},
        follow_redirects=True,
    )
    body = resp.get_data(as_text=True)
    assert "Change Order Request" in body
    assert "$1,210.00" in body  # (10*80 + 300) * 1.10
    with app.app_context():
        conv = Conversation.query.one()
        conv_id = conv.id
    r = client.post("/ai/api/send", json={"message": "How do I price concrete?", "conversation_id": conv_id})
    assert r.status_code == 200 and "Concrete" in r.get_json()["reply"]


def test_ai_tool_required_fields(client):
    register(client)
    resp = client.post("/ai/tool/rfi", data={"project": "X"}, follow_redirects=True)
    assert b"Please fill in" in resp.data


def test_chat_api_and_isolation(client, app):
    register(client)
    r = client.post("/ai/api/send", json={"message": "fall protection on a roof?"})
    data = r.get_json()
    assert r.status_code == 200 and "<strong>Safety:</strong>" in data["reply_html"]
    other = app.test_client()
    register(other, email="other@co.com", company="Other Co")
    assert other.get(f"/ai/chat/{data['conversation_id']}").status_code == 404


def test_markdown_output_is_sanitized(app):
    from buildmate import render_markdown

    html = str(render_markdown("<script>alert(1)</script> **ok** <img src=x onerror=alert(1)>"))
    assert "<script" not in html and "onerror" not in html and "<strong>ok</strong>" in html


def test_pages_render(client):
    for path in ["/", "/auth/login", "/auth/register", "/auth/forgot", "/terms", "/privacy", "/healthz"]:
        assert client.get(path).status_code == 200, path
    register(client)
    for path in ["/dashboard", "/ai/", "/ai/chat", "/ai/calculators", "/account/profile", "/account/security", "/account/company", "/account/team"]:
        assert client.get(path).status_code == 200, path
    for key in ["rfi", "daily_report", "safety", "delay", "punch_list", "estimate", "contract", "email"]:
        assert client.get(f"/ai/tool/{key}").status_code == 200, key


def test_anthropic_provider_path(client, app, monkeypatch):
    import sys
    import types

    calls = {}

    class FakeMessages:
        def create(self, **kw):
            calls.update(kw)
            return types.SimpleNamespace(content=[types.SimpleNamespace(type="text", text="**Real** answer")])

    fake = types.ModuleType("anthropic")
    fake.Anthropic = lambda api_key: types.SimpleNamespace(messages=FakeMessages())
    monkeypatch.setitem(sys.modules, "anthropic", fake)
    app.config.update(AI_PROVIDER="", ANTHROPIC_API_KEY="sk-test")

    register(client)
    r = client.post("/ai/api/send", json={"message": "hello"})
    assert r.get_json()["reply_html"] == "<p><strong>Real</strong> answer</p>"
    assert calls["model"] == app.config["ANTHROPIC_MODEL"]
    assert "Acme Builders" in calls["system"] and calls["messages"][-1] == {"role": "user", "content": "hello"}


def test_provider_error_returns_502(client, app, monkeypatch):
    from buildmate.ai import routes as ai_routes

    def boom(*a, **k):
        raise RuntimeError("down")

    monkeypatch.setattr(ai_routes, "generate_reply", boom)
    register(client)
    r = client.post("/ai/api/send", json={"message": "hello"})
    assert r.status_code == 502 and "couldn't be reached" in r.get_json()["error"]
