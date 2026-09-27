from functools import wraps

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, logout_user

from ..auth.routes import PROVIDERS, enabled_providers, normalize_email, send_verification_email
from ..extensions import db
from ..forms import (
    ChangeEmailForm,
    ChangePasswordForm,
    CompanyForm,
    DeleteAccountForm,
    InviteForm,
    ProfileForm,
    SimpleForm,
)
from ..mailer import send_email
from ..models import Invite, OAuthAccount, User
from ..security import external_url, make_token

bp = Blueprint("account", __name__, url_prefix="/account")


def company_admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not current_user.is_company_admin:
            abort(403)
        return view(*args, **kwargs)

    return login_required(wrapper)


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

@bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    form = ProfileForm(obj=current_user)
    email_form = ChangeEmailForm(prefix="email")
    if form.submit.data and form.validate_on_submit():
        current_user.full_name = form.full_name.data.strip()
        current_user.job_title = (form.job_title.data or "").strip()
        current_user.trade = form.trade.data or ""
        current_user.phone = (form.phone.data or "").strip()
        current_user.units = form.units.data
        db.session.commit()
        flash("Profile saved.", "success")
        return redirect(url_for("account.profile"))
    return render_template("account/profile.html", form=form, email_form=email_form)


@bp.route("/email", methods=["POST"])
@login_required
def change_email():
    form = ChangeEmailForm(prefix="email")
    if not form.validate_on_submit():
        for errs in form.errors.values():
            for e in errs:
                flash(e, "error")
        return redirect(url_for("account.profile"))
    if current_user.has_password and not current_user.check_password(form.password.data or ""):
        flash("Current password is incorrect.", "error")
        return redirect(url_for("account.profile"))
    new_email = normalize_email(form.new_email.data)
    if new_email == current_user.email:
        flash("That's already your email.", "info")
    elif User.query.filter_by(email=new_email).first():
        flash("That email is already used by another account.", "error")
    else:
        current_user.pending_email = new_email
        db.session.commit()
        send_verification_email(current_user, email=new_email)
        flash(f"We sent a confirmation link to {new_email}. Your email changes once you click it.", "success")
    return redirect(url_for("account.profile"))


# ---------------------------------------------------------------------------
# Security: password, linked logins, sessions, delete
# ---------------------------------------------------------------------------

@bp.route("/security", methods=["GET", "POST"])
@login_required
def security():
    pw_form = ChangePasswordForm(prefix="pw")
    delete_form = DeleteAccountForm(prefix="del")
    if pw_form.submit.data and pw_form.validate_on_submit():
        if current_user.has_password and not current_user.check_password(pw_form.current_password.data or ""):
            pw_form.current_password.errors.append("Current password is incorrect.")
        else:
            had_password = current_user.has_password
            current_user.set_password(pw_form.password.data)
            db.session.commit()
            flash("Password updated." if had_password else "Password set. You can now sign in with email too.", "success")
            return redirect(url_for("account.security"))
    return render_template(
        "account/security.html",
        pw_form=pw_form,
        delete_form=delete_form,
        action_form=SimpleForm(),
        providers=enabled_providers(),
        provider_labels={k: v["label"] for k, v in PROVIDERS.items()},
        linked=current_user.linked_providers(),
    )


@bp.route("/unlink/<provider>", methods=["POST"])
@login_required
def unlink(provider):
    if not SimpleForm().validate_on_submit():
        abort(400)
    account = OAuthAccount.query.filter_by(user_id=current_user.id, provider=provider).first_or_404()
    if current_user.login_method_count() <= 1:
        flash("Set a password first — otherwise you'd have no way to sign in.", "error")
    else:
        db.session.delete(account)
        db.session.commit()
        flash(f"{PROVIDERS.get(provider, {}).get('label', provider)} disconnected.", "success")
    return redirect(url_for("account.security"))


@bp.route("/signout-everywhere", methods=["POST"])
@login_required
def signout_everywhere():
    if not SimpleForm().validate_on_submit():
        abort(400)
    current_user.session_version += 1
    db.session.commit()
    logout_user()
    session.clear()
    flash("Signed out on all devices.", "info")
    return redirect(url_for("auth.login"))


@bp.route("/delete", methods=["POST"])
@login_required
def delete_account():
    form = DeleteAccountForm(prefix="del")
    if not form.validate_on_submit() or form.confirm_text.data.strip() != "DELETE":
        flash('Type DELETE (in capitals) to confirm.', "error")
        return redirect(url_for("account.security"))
    if current_user.has_password and not current_user.check_password(form.password.data or ""):
        flash("Current password is incorrect.", "error")
        return redirect(url_for("account.security"))
    company = current_user.company
    if company and current_user.role == "owner":
        others = company.members.filter(User.id != current_user.id).count()
        if others:
            flash("Transfer company ownership to another member before deleting your account.", "error")
            return redirect(url_for("account.team"))
    user = current_user._get_current_object()
    logout_user()
    session.clear()
    Invite.query.filter_by(invited_by_id=user.id).update({"invited_by_id": None})
    db.session.delete(user)
    db.session.flush()
    if company and company.members.count() == 0:
        db.session.delete(company)
    db.session.commit()
    flash("Your account and data have been deleted.", "info")
    return redirect(url_for("main.index"))


# ---------------------------------------------------------------------------
# Company + team
# ---------------------------------------------------------------------------

@bp.route("/company", methods=["GET", "POST"])
@login_required
def company():
    if current_user.company is None:
        return redirect(url_for("auth.onboarding"))
    form = CompanyForm(obj=current_user.company)
    if request.method == "POST":
        if not current_user.is_company_admin:
            abort(403)
        if form.validate_on_submit():
            c = current_user.company
            c.name = form.name.data.strip()
            c.industry_focus = form.industry_focus.data
            c.size = form.size.data or ""
            c.country = (form.country.data or "").strip()
            db.session.commit()
            flash("Company details saved.", "success")
            return redirect(url_for("account.company"))
    return render_template("account/company.html", form=form)


@bp.route("/team", methods=["GET", "POST"])
@login_required
def team():
    company = current_user.company
    if company is None:
        return redirect(url_for("auth.onboarding"))
    form = InviteForm()
    if request.method == "POST":
        if not current_user.is_company_admin:
            abort(403)
        if form.validate_on_submit():
            email = normalize_email(form.email.data)
            existing = User.query.filter_by(email=email).first()
            if existing and existing.company_id == company.id:
                flash(f"{email} is already on your team.", "info")
            else:
                Invite.query.filter_by(company_id=company.id, email=email, accepted_at=None).delete()
                invite = Invite(email=email, role=form.role.data, company_id=company.id, invited_by_id=current_user.id)
                db.session.add(invite)
                db.session.commit()
                link = external_url("auth.accept_invite", token=make_token("invite", {"iid": invite.id}))
                send_email(
                    email,
                    f"{current_user.display_name} invited you to {company.name}",
                    "invite",
                    dev_link=link,
                    inviter=current_user,
                    company=company,
                    link=link,
                )
                flash(f"Invite sent to {email}.", "success")
            return redirect(url_for("account.team"))
    members = company.members.order_by(User.created_at).all()
    pending = [i for i in company.invites if i.accepted_at is None]
    return render_template("account/team.html", form=form, members=members, pending=pending, action_form=SimpleForm())


def _team_member_or_404(user_id):
    member = db.session.get(User, user_id)
    if member is None or member.company_id != current_user.company_id:
        abort(404)
    return member


@bp.route("/team/<int:user_id>/role", methods=["POST"])
@company_admin_required
def set_role(user_id):
    if not SimpleForm().validate_on_submit():
        abort(400)
    member = _team_member_or_404(user_id)
    role = request.form.get("role")
    if member.role == "owner" or role not in ("admin", "member"):
        flash("That role change isn't allowed.", "error")
    else:
        member.role = role
        db.session.commit()
        flash(f"{member.display_name} is now {role}.", "success")
    return redirect(url_for("account.team"))


@bp.route("/team/<int:user_id>/remove", methods=["POST"])
@company_admin_required
def remove_member(user_id):
    if not SimpleForm().validate_on_submit():
        abort(400)
    member = _team_member_or_404(user_id)
    if member.role == "owner" or member.id == current_user.id:
        flash("You can't remove the owner or yourself.", "error")
    else:
        member.company_id = None
        member.role = "member"
        member.session_version += 1
        db.session.commit()
        flash(f"{member.display_name} was removed from the team.", "success")
    return redirect(url_for("account.team"))


@bp.route("/team/<int:user_id>/transfer", methods=["POST"])
@login_required
def transfer_ownership(user_id):
    if not SimpleForm().validate_on_submit():
        abort(400)
    if current_user.role != "owner":
        abort(403)
    member = _team_member_or_404(user_id)
    if member.id == current_user.id:
        abort(400)
    member.role = "owner"
    current_user.role = "admin"
    db.session.commit()
    flash(f"{member.display_name} now owns {member.company.name}.", "success")
    return redirect(url_for("account.team"))


@bp.route("/invites/<int:invite_id>/revoke", methods=["POST"])
@company_admin_required
def revoke_invite(invite_id):
    if not SimpleForm().validate_on_submit():
        abort(400)
    invite = db.session.get(Invite, invite_id)
    if invite is None or invite.company_id != current_user.company_id:
        abort(404)
    db.session.delete(invite)
    db.session.commit()
    flash("Invite revoked.", "success")
    return redirect(url_for("account.team"))


@bp.route("/leave", methods=["POST"])
@login_required
def leave_company():
    if not SimpleForm().validate_on_submit():
        abort(400)
    if current_user.role == "owner":
        flash("Owners must transfer ownership before leaving.", "error")
        return redirect(url_for("account.team"))
    current_user.company_id = None
    current_user.role = "member"
    db.session.commit()
    flash("You left the company. Set up your own workspace to continue.", "info")
    return redirect(url_for("auth.onboarding"))


@bp.app_context_processor
def inject_mail_mode():
    return {"smtp_configured": bool(current_app.config.get("MAIL_SERVER"))}
