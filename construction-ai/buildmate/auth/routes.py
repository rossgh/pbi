from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from ..extensions import db, oauth
from ..forms import ForgotPasswordForm, LoginForm, OnboardingForm, RegisterForm, ResetPasswordForm
from ..mailer import send_email
from ..models import Company, Invite, OAuthAccount, User, utcnow
from ..security import external_url, is_safe_next, make_token, read_token

bp = Blueprint("auth", __name__, url_prefix="/auth")

PROVIDERS = {
    "google": {"label": "Google"},
    "microsoft": {"label": "Microsoft"},
}


def enabled_providers():
    cfg = current_app.config
    out = []
    if cfg.get("GOOGLE_CLIENT_ID") and cfg.get("GOOGLE_CLIENT_SECRET"):
        out.append("google")
    if cfg.get("MICROSOFT_CLIENT_ID") and cfg.get("MICROSOFT_CLIENT_SECRET"):
        out.append("microsoft")
    return out


def normalize_email(email):
    return (email or "").strip().lower()


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def send_verification_email(user, email=None):
    email = email or user.email
    token = make_token("verify-email", {"uid": user.id, "email": email})
    link = external_url("auth.verify_email", token=token)
    send_email(email, "Confirm your email", "verify_email", dev_link=link, user=user, link=link)


def _pending_invite():
    token = session.get("invite_token")
    if not token:
        return None
    payload = read_token("invite", token, current_app.config["INVITE_TOKEN_MAX_AGE"])
    invite = db.session.get(Invite, payload["iid"]) if payload else None
    if invite is None or invite.accepted_at is not None:
        session.pop("invite_token", None)
        return None
    return invite


def apply_invite(user, invite):
    """Move ``user`` into the invite's company. Returns an error string or None."""
    if normalize_email(invite.email) != normalize_email(user.email):
        return f"This invite was sent to {invite.email}. Sign in with that email to accept it."
    old_company = user.company
    if old_company and old_company.id != invite.company_id:
        others = old_company.members.filter(User.id != user.id).count()
        if others and user.role == "owner":
            return "You own a company with other members. Transfer ownership before joining another company."
    user.company_id = invite.company_id
    user.role = invite.role
    invite.accepted_at = utcnow()
    db.session.flush()
    if old_company and old_company.id != invite.company_id and old_company.members.count() == 0:
        db.session.delete(old_company)
    db.session.commit()
    return None


def finish_login(user, remember=False):
    user.register_successful_login()
    db.session.commit()
    login_user(user, remember=remember)
    session.permanent = remember

    invite = _pending_invite()
    if invite:
        err = apply_invite(user, invite)
        session.pop("invite_token", None)
        if err:
            flash(err, "error")
        else:
            flash(f"You've joined {invite.company.name}.", "success")

    if user.company_id is None:
        return redirect(url_for("auth.onboarding"))
    nxt = session.pop("next_url", None) or request.args.get("next")
    if is_safe_next(nxt):
        return redirect(nxt)
    return redirect(url_for("main.dashboard"))


# ---------------------------------------------------------------------------
# Email + password
# ---------------------------------------------------------------------------

@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    form = LoginForm()
    if request.method == "GET" and is_safe_next(request.args.get("next")):
        session["next_url"] = request.args["next"]
    if form.validate_on_submit():
        cfg = current_app.config
        user = User.query.filter_by(email=normalize_email(form.email.data)).first()
        if user and user.is_locked():
            flash(f"Too many failed attempts. Try again in {cfg['LOCKOUT_MINUTES']} minutes or reset your password.", "error")
        elif user and user.check_password(form.password.data):
            return finish_login(user, remember=form.remember.data)
        else:
            if user:
                user.register_failed_login(cfg["MAX_FAILED_LOGINS"], cfg["LOCKOUT_MINUTES"])
                db.session.commit()
                if not user.has_password and user.oauth_accounts:
                    names = ", ".join(PROVIDERS[a.provider]["label"] for a in user.oauth_accounts)
                    flash(f"This account signs in with {names}. Use that button, or reset your password to add one.", "info")
            flash("Incorrect email or password.", "error")
    return render_template("auth/login.html", form=form, providers=enabled_providers())


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    form = RegisterForm()
    invite = _pending_invite()
    if request.method == "GET" and invite:
        form.email.data = invite.email
    if form.validate_on_submit():
        email = normalize_email(form.email.data)
        if User.query.filter_by(email=email).first():
            flash("An account with that email already exists. Sign in, or reset your password.", "error")
            return redirect(url_for("auth.login"))
        if not invite and not (form.company_name.data or "").strip():
            form.company_name.errors.append("Company name is required.")
            return render_template("auth/register.html", form=form, providers=enabled_providers(), invite=invite)

        user = User(email=email, full_name=form.full_name.data.strip(), trade=form.trade.data or "")
        user.set_password(form.password.data)
        if not invite:
            company = Company(name=form.company_name.data.strip())
            db.session.add(company)
            db.session.flush()
            user.company_id = company.id
            user.role = "owner"
        db.session.add(user)
        db.session.commit()
        send_verification_email(user)
        flash("Welcome aboard! Check your inbox to confirm your email.", "success")
        return finish_login(user)
    return render_template("auth/register.html", form=form, providers=enabled_providers(), invite=invite)


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    session.clear()
    flash("You've been signed out.", "info")
    return redirect(url_for("auth.login"))


@bp.route("/verify/<token>")
def verify_email(token):
    payload = read_token("verify-email", token, current_app.config["VERIFY_TOKEN_MAX_AGE"])
    user = db.session.get(User, payload["uid"]) if payload else None
    if user is None:
        flash("That confirmation link is invalid or has expired.", "error")
        return redirect(url_for("main.index"))

    email = normalize_email(payload["email"])
    if email != user.email:
        # Email-change confirmation
        if user.pending_email != email:
            flash("That confirmation link is no longer valid.", "error")
            return redirect(url_for("main.index"))
        if User.query.filter(User.email == email, User.id != user.id).first():
            flash("That email is already used by another account.", "error")
            return redirect(url_for("main.index"))
        user.email = email
        user.pending_email = None
    user.email_verified = True
    db.session.commit()
    flash("Email confirmed. Thanks!", "success")
    return redirect(url_for("main.dashboard") if current_user.is_authenticated else url_for("auth.login"))


@bp.route("/verify/resend", methods=["POST"])
@login_required
def resend_verification():
    if current_user.email_verified:
        flash("Your email is already confirmed.", "info")
    else:
        send_verification_email(current_user)
        flash("Confirmation email sent.", "success")
    return redirect(request.referrer if is_safe_next(request.referrer) else url_for("main.dashboard"))


@bp.route("/forgot", methods=["GET", "POST"])
def forgot_password():
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=normalize_email(form.email.data)).first()
        if user:
            token = make_token("reset-password", {"uid": user.id, "fp": user.password_fingerprint()})
            link = external_url("auth.reset_password", token=token)
            send_email(user.email, "Reset your password", "reset_password", dev_link=link, user=user, link=link)
        # Same message either way so the form can't be used to discover accounts.
        flash("If an account exists for that email, a reset link is on its way.", "info")
        return redirect(url_for("auth.login"))
    return render_template("auth/forgot.html", form=form)


@bp.route("/reset/<token>", methods=["GET", "POST"])
def reset_password(token):
    payload = read_token("reset-password", token, current_app.config["RESET_TOKEN_MAX_AGE"])
    user = db.session.get(User, payload["uid"]) if payload else None
    if user is None or payload.get("fp") != user.password_fingerprint():
        flash("That reset link is invalid, expired, or already used.", "error")
        return redirect(url_for("auth.forgot_password"))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        user.session_version += 1  # sign out every other session
        user.failed_logins = 0
        user.locked_until = None
        user.email_verified = True  # they proved control of the inbox
        db.session.commit()
        logout_user()
        flash("Password updated. Please sign in.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/reset.html", form=form)


# ---------------------------------------------------------------------------
# Company onboarding and invites
# ---------------------------------------------------------------------------

@bp.route("/onboarding", methods=["GET", "POST"])
@login_required
def onboarding():
    if current_user.company_id:
        return redirect(url_for("main.dashboard"))
    form = OnboardingForm()
    if request.method == "GET":
        form.trade.data = current_user.trade
    if form.validate_on_submit():
        company = Company(name=form.company_name.data.strip(), industry_focus=form.industry_focus.data, size=form.size.data or "")
        db.session.add(company)
        db.session.flush()
        current_user.company_id = company.id
        current_user.role = "owner"
        if form.trade.data:
            current_user.trade = form.trade.data
        db.session.commit()
        flash(f"{company.name} is set up. Let's get to work.", "success")
        return redirect(url_for("main.dashboard"))
    return render_template("auth/onboarding.html", form=form)


@bp.route("/invite/<token>")
def accept_invite(token):
    payload = read_token("invite", token, current_app.config["INVITE_TOKEN_MAX_AGE"])
    invite = db.session.get(Invite, payload["iid"]) if payload else None
    if invite is None or invite.accepted_at is not None:
        flash("That invite link is invalid, expired, or already used.", "error")
        return redirect(url_for("main.index"))
    session["invite_token"] = token
    if current_user.is_authenticated:
        err = apply_invite(current_user, invite)
        session.pop("invite_token", None)
        if err:
            flash(err, "error")
        else:
            flash(f"You've joined {invite.company.name}.", "success")
        return redirect(url_for("main.dashboard"))
    if User.query.filter_by(email=normalize_email(invite.email)).first():
        flash(f"Sign in to join {invite.company.name}.", "info")
        return redirect(url_for("auth.login"))
    flash(f"Create your account to join {invite.company.name}.", "info")
    return redirect(url_for("auth.register"))


# ---------------------------------------------------------------------------
# OAuth (Google, Microsoft)
# ---------------------------------------------------------------------------

def fetch_oauth_profile(provider):
    """Complete the OAuth code exchange and return a normalized profile dict."""
    client = oauth.create_client(provider)
    if provider == "microsoft":
        token = client.authorize_access_token(claims_options={"iss": {"essential": True}})
        info = token.get("userinfo") or {}
        # Multi-tenant endpoint: the issuer carries the user's tenant id.
        issuer_tpl = client.load_server_metadata().get("issuer", "")
        expected = issuer_tpl.replace("{tenantid}", info.get("tid", ""))
        if not info.get("iss") or info.get("iss") != expected:
            raise ValueError("Unexpected token issuer")
        return {
            "sub": info.get("oid") or info["sub"],
            "email": info.get("email") or info.get("preferred_username"),
            # Microsoft does not guarantee the email claim is verified.
            "email_verified": False,
            "name": info.get("name", ""),
        }
    token = client.authorize_access_token()
    info = token.get("userinfo") or client.userinfo()
    return {
        "sub": info["sub"],
        "email": info.get("email"),
        "email_verified": bool(info.get("email_verified")),
        "name": info.get("name", ""),
    }


@bp.route("/oauth/<provider>")
def oauth_start(provider):
    if provider not in enabled_providers():
        abort(404)
    session["oauth_link"] = current_user.is_authenticated
    redirect_uri = external_url("auth.oauth_callback", provider=provider)
    kwargs = {"prompt": "select_account"}
    return oauth.create_client(provider).authorize_redirect(redirect_uri, **kwargs)


@bp.route("/oauth/<provider>/callback")
def oauth_callback(provider):
    if provider not in enabled_providers():
        abort(404)
    label = PROVIDERS[provider]["label"]
    linking = session.pop("oauth_link", False) and current_user.is_authenticated
    fail_to = url_for("account.security") if linking else url_for("auth.login")
    try:
        profile = fetch_oauth_profile(provider)
    except Exception:  # noqa: BLE001 — any provider/network error ends the flow the same way
        current_app.logger.exception("OAuth callback failed for %s", provider)
        flash(f"{label} sign-in didn't complete. Please try again.", "error")
        return redirect(fail_to)

    sub = str(profile["sub"])
    email = normalize_email(profile.get("email"))
    account = OAuthAccount.query.filter_by(provider=provider, provider_user_id=sub).first()

    if linking:
        if account and account.user_id != current_user.id:
            flash(f"That {label} account is already connected to a different user.", "error")
        elif account:
            flash(f"{label} is already connected.", "info")
        else:
            db.session.add(OAuthAccount(provider=provider, provider_user_id=sub, email=email, user=current_user))
            db.session.commit()
            flash(f"{label} connected. You can now sign in with it.", "success")
        return redirect(url_for("account.security"))

    if account:
        return finish_login(account.user, remember=True)

    if not email:
        flash(f"{label} didn't share an email address, so we couldn't sign you in.", "error")
        return redirect(fail_to)

    user = User.query.filter_by(email=email).first()
    if user:
        if not profile["email_verified"]:
            flash(
                f"An account with {email} already exists. Sign in with your password, then connect {label} "
                "from Settings → Security.",
                "error",
            )
            return redirect(url_for("auth.login"))
        db.session.add(OAuthAccount(provider=provider, provider_user_id=sub, email=email, user=user))
        user.email_verified = True
        db.session.commit()
        return finish_login(user, remember=True)

    user = User(email=email, full_name=profile.get("name") or "", email_verified=profile["email_verified"])
    db.session.add(user)
    db.session.add(OAuthAccount(provider=provider, provider_user_id=sub, email=email, user=user))
    db.session.commit()
    if not user.email_verified:
        send_verification_email(user)
    flash(f"Account created with {label}.", "success")
    return finish_login(user, remember=True)
