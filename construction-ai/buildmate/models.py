import hashlib
from datetime import datetime, timedelta, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db, login_manager


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


ROLES = ("owner", "admin", "member")

TRADES = [
    "General Contractor",
    "Project Manager",
    "Site Superintendent",
    "Estimator",
    "Safety Officer",
    "Architect / Designer",
    "Engineer",
    "Subcontractor",
    "Electrician",
    "Plumber",
    "HVAC",
    "Carpenter",
    "Concrete / Masonry",
    "Owner / Developer",
    "Other",
]


class Company(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    industry_focus = db.Column(db.String(80), default="General construction")
    size = db.Column(db.String(40), default="")
    country = db.Column(db.String(80), default="")
    created_at = db.Column(db.DateTime, default=utcnow)

    members = db.relationship("User", back_populates="company", lazy="dynamic")
    invites = db.relationship("Invite", back_populates="company", cascade="all, delete-orphan")


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255))
    full_name = db.Column(db.String(120), default="")
    job_title = db.Column(db.String(120), default="")
    trade = db.Column(db.String(80), default="")
    phone = db.Column(db.String(40), default="")
    units = db.Column(db.String(10), default="imperial")  # imperial | metric
    email_verified = db.Column(db.Boolean, default=False)
    pending_email = db.Column(db.String(255))
    role = db.Column(db.String(20), default="member")
    company_id = db.Column(db.Integer, db.ForeignKey("company.id"))
    # Bumped to invalidate every existing session ("sign out everywhere", password reset).
    session_version = db.Column(db.Integer, default=1, nullable=False)
    failed_logins = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=utcnow)
    last_login_at = db.Column(db.DateTime)

    company = db.relationship("Company", back_populates="members")
    oauth_accounts = db.relationship("OAuthAccount", back_populates="user", cascade="all, delete-orphan")
    conversations = db.relationship("Conversation", back_populates="user", cascade="all, delete-orphan")

    # --- Flask-Login -----------------------------------------------------
    def get_id(self):
        return f"{self.id}:{self.session_version}"

    # --- passwords -------------------------------------------------------
    @property
    def has_password(self):
        return bool(self.password_hash)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return bool(self.password_hash) and check_password_hash(self.password_hash, password)

    def password_fingerprint(self):
        """Short digest of the current hash; embedding it in reset tokens makes them single-use."""
        return hashlib.sha256((self.password_hash or "none").encode()).hexdigest()[:16]

    # --- lockout ---------------------------------------------------------
    def is_locked(self):
        return self.locked_until is not None and self.locked_until > utcnow()

    def register_failed_login(self, max_attempts, lock_minutes):
        self.failed_logins = (self.failed_logins or 0) + 1
        if self.failed_logins >= max_attempts:
            self.locked_until = utcnow() + timedelta(minutes=lock_minutes)
            self.failed_logins = 0

    def register_successful_login(self):
        self.failed_logins = 0
        self.locked_until = None
        self.last_login_at = utcnow()

    # --- helpers ---------------------------------------------------------
    @property
    def display_name(self):
        return self.full_name or self.email.split("@")[0]

    @property
    def initials(self):
        parts = [p for p in (self.full_name or self.email).replace("@", " ").split() if p]
        return "".join(p[0] for p in parts[:2]).upper() or "?"

    @property
    def is_company_admin(self):
        return self.role in ("owner", "admin")

    def linked_providers(self):
        return {a.provider for a in self.oauth_accounts}

    def login_method_count(self):
        return len(self.oauth_accounts) + (1 if self.has_password else 0)


class OAuthAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(30), nullable=False)
    provider_user_id = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255))
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow)

    user = db.relationship("User", back_populates="oauth_accounts")

    __table_args__ = (db.UniqueConstraint("provider", "provider_user_id"),)


class Invite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="member")
    company_id = db.Column(db.Integer, db.ForeignKey("company.id"), nullable=False)
    invited_by_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    accepted_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=utcnow)

    company = db.relationship("Company", back_populates="invites")
    invited_by = db.relationship("User")


class Conversation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    tool = db.Column(db.String(40), default="assistant")
    title = db.Column(db.String(200), default="New conversation")
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    user = db.relationship("User", back_populates="conversations")
    messages = db.relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.id"
    )


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey("conversation.id"), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # user | assistant
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow)

    conversation = db.relationship("Conversation", back_populates="messages")


@login_manager.user_loader
def load_user(user_id):
    try:
        uid, version = user_id.split(":")
        user = db.session.get(User, int(uid))
    except (ValueError, AttributeError):
        return None
    if user is None or str(user.session_version) != version:
        return None
    return user
