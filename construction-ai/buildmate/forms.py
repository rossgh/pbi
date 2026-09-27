from flask_wtf import FlaskForm
from wtforms import BooleanField, EmailField, PasswordField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional, ValidationError

from .models import TRADES
from .security import password_problems


def strong_password(form, field):
    problems = password_problems(field.data or "")
    if problems:
        raise ValidationError("Password needs " + ", ".join(problems) + ".")


TRADE_CHOICES = [("", "Select your role…")] + [(t, t) for t in TRADES]
SIZE_CHOICES = [("", "Company size…"), ("1-10", "1–10"), ("11-50", "11–50"), ("51-200", "51–200"), ("201+", "201+")]
FOCUS_CHOICES = [
    ("General construction", "General construction"),
    ("Residential", "Residential"),
    ("Commercial", "Commercial"),
    ("Industrial", "Industrial"),
    ("Civil / Infrastructure", "Civil / Infrastructure"),
    ("Specialty trade", "Specialty trade"),
    ("Renovation / Remodel", "Renovation / Remodel"),
]


class LoginForm(FlaskForm):
    email = EmailField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    remember = BooleanField("Keep me signed in")
    submit = SubmitField("Sign in")


class RegisterForm(FlaskForm):
    full_name = StringField("Full name", validators=[DataRequired(), Length(max=120)])
    email = EmailField("Work email", validators=[DataRequired(), Email(), Length(max=255)])
    company_name = StringField("Company name", validators=[Optional(), Length(max=160)])
    trade = SelectField("Your role", choices=TRADE_CHOICES, validators=[Optional()])
    password = PasswordField("Password", validators=[DataRequired(), strong_password])
    confirm = PasswordField("Confirm password", validators=[DataRequired(), EqualTo("password", "Passwords must match.")])
    accept_terms = BooleanField("I agree to the Terms and Privacy Policy", validators=[DataRequired("Please accept the terms.")])
    submit = SubmitField("Create account")


class ForgotPasswordForm(FlaskForm):
    email = EmailField("Email", validators=[DataRequired(), Email()])
    submit = SubmitField("Send reset link")


class ResetPasswordForm(FlaskForm):
    password = PasswordField("New password", validators=[DataRequired(), strong_password])
    confirm = PasswordField("Confirm new password", validators=[DataRequired(), EqualTo("password", "Passwords must match.")])
    submit = SubmitField("Reset password")


class OnboardingForm(FlaskForm):
    company_name = StringField("Company name", validators=[DataRequired(), Length(max=160)])
    industry_focus = SelectField("Main type of work", choices=FOCUS_CHOICES)
    size = SelectField("Company size", choices=SIZE_CHOICES, validators=[Optional()])
    trade = SelectField("Your role", choices=TRADE_CHOICES, validators=[Optional()])
    submit = SubmitField("Continue")


class ProfileForm(FlaskForm):
    full_name = StringField("Full name", validators=[DataRequired(), Length(max=120)])
    job_title = StringField("Job title", validators=[Optional(), Length(max=120)])
    trade = SelectField("Role / trade", choices=TRADE_CHOICES, validators=[Optional()])
    phone = StringField("Phone", validators=[Optional(), Length(max=40)])
    units = SelectField("Preferred units", choices=[("imperial", "Imperial (ft, yd³, lb)"), ("metric", "Metric (m, m³, kg)")])
    submit = SubmitField("Save profile")


class ChangeEmailForm(FlaskForm):
    new_email = EmailField("New email", validators=[DataRequired(), Email(), Length(max=255)])
    password = PasswordField("Current password", validators=[Optional()])
    submit = SubmitField("Send confirmation")


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField("Current password", validators=[Optional()])
    password = PasswordField("New password", validators=[DataRequired(), strong_password])
    confirm = PasswordField("Confirm new password", validators=[DataRequired(), EqualTo("password", "Passwords must match.")])
    submit = SubmitField("Update password")


class DeleteAccountForm(FlaskForm):
    confirm_text = StringField('Type "DELETE" to confirm', validators=[DataRequired()])
    password = PasswordField("Current password", validators=[Optional()])
    submit = SubmitField("Delete my account")


class CompanyForm(FlaskForm):
    name = StringField("Company name", validators=[DataRequired(), Length(max=160)])
    industry_focus = SelectField("Main type of work", choices=FOCUS_CHOICES)
    size = SelectField("Company size", choices=SIZE_CHOICES, validators=[Optional()])
    country = StringField("Country / region", validators=[Optional(), Length(max=80)])
    submit = SubmitField("Save company")


class InviteForm(FlaskForm):
    email = EmailField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    role = SelectField("Role", choices=[("member", "Member"), ("admin", "Admin")])
    submit = SubmitField("Send invite")


class SimpleForm(FlaskForm):
    """CSRF-only form for button actions."""
