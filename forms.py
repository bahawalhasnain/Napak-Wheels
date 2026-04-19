from flask_wtf import FlaskForm
from flask_wtf.file import MultipleFileField, FileAllowed
from wtforms import (
    StringField,
    IntegerField,
    FloatField,
    SelectField,
    TextAreaField,
    BooleanField,
    PasswordField,
    HiddenField,
)
from wtforms.validators import DataRequired, Email, NumberRange, Length, EqualTo, Optional


class CarForm(FlaskForm):
    make = StringField('Make', validators=[DataRequired(), Length(max=50)])
    model = StringField('Model', validators=[DataRequired(), Length(max=50)])
    year = IntegerField('Year', validators=[DataRequired(), NumberRange(min=1900, max=2025)])
    price = FloatField('Price (PKR)', validators=[DataRequired(), NumberRange(min=0)])
    mileage = IntegerField('Mileage', validators=[DataRequired(), NumberRange(min=0)])
    color = StringField('Color', validators=[DataRequired(), Length(max=30)])
    fuel_type = SelectField('Fuel Type', 
                           choices=[('Gasoline', 'Gasoline'), ('Diesel', 'Diesel'), 
                                   ('Hybrid', 'Hybrid'), ('Electric', 'Electric')],
                           validators=[DataRequired()])
    transmission = SelectField('Transmission',
                              choices=[('Manual', 'Manual'), ('Automatic', 'Automatic'), 
                                      ('CVT', 'CVT')],
                              validators=[DataRequired()])
    engine_size = StringField('Engine Size (L)', validators=[Length(max=10)])
    description = TextAreaField('Description', validators=[Length(max=1000)])
    seller_name = StringField('Your Name', validators=[Optional(), Length(max=100)])
    seller_phone = StringField('Phone Number', validators=[DataRequired(), Length(max=20)])
    seller_email = StringField('Email', validators=[Optional(), Email(), Length(max=100)])
    location = StringField('Location', validators=[DataRequired(), Length(max=100)])
    photos = MultipleFileField('Car Photos', validators=[FileAllowed(['jpg', 'jpeg', 'png', 'gif', 'jfif'], 'Images only!')])
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
    fuel_type = SelectField('Fuel Type', 
                           choices=[('', 'Any Fuel Type'), ('Gasoline', 'Gasoline'), 
                                   ('Diesel', 'Diesel'), ('Hybrid', 'Hybrid'), 
                                   ('Electric', 'Electric')])


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
