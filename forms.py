from datetime import date

from flask_wtf import FlaskForm
from flask_wtf.file import MultipleFileField, FileAllowed
from wtforms import (
    BooleanField,
    DateTimeLocalField,
    FloatField,
    HiddenField,
    IntegerField,
    PasswordField,
    SelectField,
    StringField,
    TextAreaField,
)
from wtforms.validators import (
    DataRequired,
    Email,
    EqualTo,
    Length,
    NumberRange,
    Optional,
    ValidationError,
)


class ModelYear:
    """Allow 1900 .. current calendar year (evaluated when the form is validated)."""

    def __init__(self, min_year: int = 1900):
        self.min_year = min_year

    def __call__(self, form, field):
        if field.data is None:
            return
        max_y = date.today().year
        if field.data < self.min_year or field.data > max_y:
            raise ValidationError(f"Year must be between {self.min_year} and {max_y}.")


class CarForm(FlaskForm):
    make = StringField('Make', validators=[DataRequired(), Length(max=50)])
    model = StringField('Model', validators=[DataRequired(), Length(max=50)])
    year = IntegerField('Year', validators=[DataRequired(), ModelYear()])
    price = FloatField('Price (PKR)', validators=[DataRequired(), NumberRange(min=0)])
    mileage = IntegerField('Mileage', validators=[DataRequired(), NumberRange(min=0)])
    color = StringField('Color', validators=[DataRequired(), Length(max=30)])
    fuel_type = SelectField(
        'Fuel Type',
        choices=[('Gasoline', 'Gasoline'), ('Diesel', 'Diesel'),
                 ('Hybrid', 'Hybrid'), ('Electric', 'Electric')],
        validators=[DataRequired()],
    )
    transmission = SelectField(
        'Transmission',
        choices=[('Manual', 'Manual'), ('Automatic', 'Automatic'), ('CVT', 'CVT')],
        validators=[DataRequired()],
    )
    engine_size = StringField('Engine Size (L)', validators=[Length(max=10)])
    description = TextAreaField('Description', validators=[Length(max=1000)])
    seller_name = StringField('Your Name', validators=[Optional(), Length(max=100)])
    seller_phone = StringField('Phone Number', validators=[DataRequired(), Length(max=20)])
    seller_email = StringField('Email', validators=[Optional(), Email(), Length(max=100)])
    location = StringField('Location', validators=[DataRequired(), Length(max=100)])
    photos = MultipleFileField(
        'Car Photos',
        validators=[FileAllowed(['jpg', 'jpeg', 'png', 'gif', 'jfif'], 'Images only!')],
    )
    features = HiddenField('Features')


class EditCarForm(CarForm):
    is_sold = BooleanField('Mark as Sold')


class SearchForm(FlaskForm):
    search = StringField('Search')
    make = SelectField('Make', choices=[('', 'Any Make')])
    min_price = FloatField('Min Price')
    max_price = FloatField('Max Price')
    min_year = IntegerField('Min Year')
    max_year = IntegerField('Max Year')
    fuel_type = SelectField(
        'Fuel Type',
        choices=[('', 'Any Fuel Type'), ('Gasoline', 'Gasoline'),
                 ('Diesel', 'Diesel'), ('Hybrid', 'Hybrid'), ('Electric', 'Electric')],
    )


class SignUpForm(FlaskForm):
    full_name = StringField('Full Name', validators=[DataRequired(), Length(max=120)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    phone = StringField('Phone Number', validators=[DataRequired(), Length(max=20)])
    location = StringField('Location', validators=[DataRequired(), Length(max=100)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8, max=128)])
    confirm_password = PasswordField(
        'Confirm Password',
        validators=[DataRequired(), EqualTo('password', message='Passwords must match')],
    )


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8, max=128)])
    remember = BooleanField('Remember me', default=False)


# ---------------------------------------------------------------------------
# Account / profile / settings
# ---------------------------------------------------------------------------


class ProfileForm(FlaskForm):
    full_name = StringField('Full name', validators=[DataRequired(), Length(max=120)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    phone = StringField('Phone number', validators=[Optional(), Length(max=20)])
    location = StringField('Location', validators=[Optional(), Length(max=100)])


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField(
        'Current password', validators=[DataRequired(), Length(min=8, max=128)]
    )
    new_password = PasswordField(
        'New password', validators=[DataRequired(), Length(min=8, max=128)]
    )
    confirm_password = PasswordField(
        'Confirm new password',
        validators=[DataRequired(), EqualTo('new_password', message='Passwords must match')],
    )


class NotificationPrefsForm(FlaskForm):
    email_alerts_enabled = BooleanField(
        'Email me when a saved search matches a new listing', default=True
    )


class DeleteAccountForm(FlaskForm):
    confirm_password = PasswordField(
        'Confirm with your password', validators=[DataRequired(), Length(min=8, max=128)]
    )
    confirm_text = StringField(
        'Type DELETE to confirm', validators=[DataRequired(), Length(max=10)]
    )


# ---------------------------------------------------------------------------
# Messaging / offers / test drives / saved searches / reports
# ---------------------------------------------------------------------------


class MessageForm(FlaskForm):
    body = TextAreaField('Message', validators=[DataRequired(), Length(min=1, max=2000)])


class OfferForm(FlaskForm):
    amount = FloatField('Offer amount (PKR)', validators=[DataRequired(), NumberRange(min=1)])
    note = TextAreaField('Note to seller', validators=[Optional(), Length(max=1000)])


class CounterOfferForm(FlaskForm):
    amount = FloatField('Counter offer (PKR)', validators=[DataRequired(), NumberRange(min=1)])
    note = TextAreaField('Note', validators=[Optional(), Length(max=1000)])


class TestDriveRequestForm(FlaskForm):
    requested_at = DateTimeLocalField(
        'Preferred date & time',
        format='%Y-%m-%dT%H:%M',
        validators=[DataRequired()],
    )
    duration_minutes = IntegerField(
        'Duration (minutes)',
        default=30,
        validators=[DataRequired(), NumberRange(min=15, max=240)],
    )
    location = StringField('Meeting location', validators=[Optional(), Length(max=200)])
    message = TextAreaField('Message to seller', validators=[Optional(), Length(max=1000)])


class TestDriveResponseForm(FlaskForm):
    seller_response = TextAreaField('Response (optional)', validators=[Optional(), Length(max=1000)])


class SavedSearchForm(FlaskForm):
    name = StringField('Search name', validators=[DataRequired(), Length(max=120)])
    alerts_enabled = BooleanField('Email me when matching cars are posted', default=True)


class ReportForm(FlaskForm):
    from models import Report

    reason = SelectField(
        'Reason',
        choices=Report.REASONS,
        validators=[DataRequired()],
    )
    details = TextAreaField('Additional details', validators=[Optional(), Length(max=1000)])


class ReportReviewForm(FlaskForm):
    review_note = TextAreaField('Internal note', validators=[Optional(), Length(max=2000)])
