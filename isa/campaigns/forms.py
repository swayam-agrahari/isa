from flask_wtf import FlaskForm

from isa.utils.languages import getLanguages
from wtforms import BooleanField, SelectField, StringField, SubmitField, widgets, Label, DecimalField, HiddenField
from wtforms.fields.html5 import DateField
from wtforms.validators import DataRequired, InputRequired, Length, NumberRange


class CampaignForm(FlaskForm):
    campaign_name = StringField(validators=[DataRequired(),
                                Length(min=2, max=20)])
    short_description = StringField(validators=[DataRequired()], widget=widgets.TextArea())
    start_date = StringField(id='start_date_datepicker', validators=[InputRequired()])
    end_date = StringField(id='end_date_datepicker')
    categories = HiddenField()
    campaign_images = HiddenField()
    depicts_metadata = BooleanField()
    captions_metadata = BooleanField()
    campaign_type = BooleanField()
    campaign_image = StringField('Campaign Image')
    long_description = StringField(widget=widgets.TextArea())
    update_images = BooleanField()
    submit = SubmitField()


class CaptionsLanguageForm(FlaskForm):
    language_select_1 = SelectField(validators=[DataRequired()], choices=getLanguages())
    language_select_2 = SelectField(validators=[DataRequired()], choices=getLanguages())
    language_select_3 = SelectField(validators=[DataRequired()], choices=getLanguages())
    language_select_4 = SelectField(validators=[DataRequired()], choices=getLanguages())
    language_select_5 = SelectField(validators=[DataRequired()], choices=getLanguages())
    language_select_6 = SelectField(validators=[DataRequired()], choices=getLanguages())
    submit = SubmitField()
