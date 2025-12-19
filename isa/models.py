from datetime import datetime

from flask_login import UserMixin
from sqlalchemy import event, select

from isa import db, login_manager


@login_manager.user_loader
def user_loader(user_id):
    return User.query.get(int(user_id))


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True, index=True)
    username = db.Column(db.String(255), unique=True, nullable=False)
    caption_languages = db.Column(db.String(25), nullable=False)
    # Maximum length for language code is 13 because that's the
    # maximum length in MediaWiki\Languages\Data\Names.
    depicts_language = db.Column(db.String(13), nullable=False, default='')
    contrib = db.Column(db.Integer, default=0)
    managed_campaigns = db.relationship('Campaign', backref='user', lazy=True)
    suggestion = db.relationship('Suggestion', backref='user', lazy=True)

    def __repr__(self):
        # This is what is shown when object is printed
        return "User({}, {})".format(
               self.username,
               self.caption_languages)


class Contribution(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref='contribution', lazy=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaign.id'), nullable=False)
    file = db.Column(db.String(210), nullable=False)
    edit_type = db.Column(db.String(10), nullable=False)
    edit_action = db.Column(db.String(7), nullable=False)
    country = db.Column(db.String(50), nullable=False, default='')
    depict_item = db.Column(db.String(15), nullable=True)
    depict_prominent = db.Column(db.Boolean, nullable=True)
    caption_language = db.Column(db.String(5), nullable=True)
    caption_text = db.Column(db.String(200), nullable=True)
    date = db.Column(db.Date, nullable=False,
                     default=datetime.now().strftime('%Y-%m-%d'))

    def __repr__(self):
        # This is what is shown when object is printed
        return "Contribution( {}, {}, {},{},{},{})".format(
               self.user_id,
               self.campaign_id,
               self.file,
               self.edit_type,
               self.edit_action,
               self.country)

    def __getitem__(self, index):
        return self[index]


class Campaign(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    campaign_name = db.Column(db.String(200), nullable=False)
    campaign_images = db.Column(db.Integer, default=0)
    images = db.relationship('Image', backref='campaign', lazy=True)
    update_status = db.Column(db.Integer, default=0)
    campaign_contributions = db.Column(db.Integer, default=0)
    campaign_participants = db.Column(db.Integer, default=0)
    campaign_image = db.Column(db.String(200), nullable=True, default='')
    categories = db.Column(db.Text, nullable=False)
    start_date = db.Column(db.Date, nullable=False,
                           default=datetime.now().strftime('%Y-%m-%d'))
    campaign_manager = db.Column(db.String(15))
    manager_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    manager = db.relationship('User', backref='campaign', lazy=True)
    end_date = db.Column(db.Date, nullable=True,
                         default=None)
    status = db.Column(db.Boolean, nullable=False, default=bool('False'))
    short_description = db.Column(db.Text, nullable=False)
    long_description = db.Column(db.Text, nullable=False)
    categories = db.Column(db.Text, nullable=False)
    creation_date = db.Column(db.Date, nullable=True,
                              default=datetime.now().strftime('%Y-%m-%d'))
    campaign_type = db.Column(db.Boolean)
    depicts_metadata = db.Column(db.Boolean)
    captions_metadata = db.Column(db.Boolean)
    contribution = db.relationship('Contribution', backref='made_on', lazy=True)

    def __repr__(self):
        # This is what is shown when object is printed
        return "Campaign( {}, {}, {}, {}, {}, {}, {}, {})".format(
               self.campaign_name,
               self.campaign_image,
               self.campaign_manager,
               self.categories,
               self.captions_metadata,
               self.creation_date,
               self.start_date,
               self.end_date)


@event.listens_for(Campaign, 'before_insert')
def _ensure_campaign_manager_id(mapper, connection, target):
    """Ensure ``Campaign.manager_id`` is populated when only ``campaign_manager`` is set.

    This hook is executed during SQLAlchemy's flush process, so it *must not*
    call ``Session.add`` or ``Session.flush``.  To avoid nested flushes we work
    directly with the low-level ``connection`` and the ``User`` table instead
    of going through the ORM session.
    """

    # If the caller already supplied a manager_id we respect it.
    if target.manager_id is not None:
        return

    username = getattr(target, 'campaign_manager', None)
    if not username:
        # Nothing to derive a manager from; leave the value unchanged and let
        # the database enforce integrity if this is really invalid.
        return

    user_table = User.__table__

    # Look for an existing user with this username using the same connection
    # that SQLAlchemy is currently flushing with.
    existing = connection.execute(
        select(user_table.c.id).where(user_table.c.username == username)
    ).first()

    if existing is not None:
        target.manager_id = existing[0]
        return

    # No existing user row; insert a minimal one and use its primary key.
    insert_stmt = user_table.insert().values(
        username=username,
        caption_languages='en',  # required column; default to English
    )
    result = connection.execute(insert_stmt)
    user_id = None

    # ``inserted_primary_key`` is populated on most dialects; fall back to a
    # SELECT if it isn't available for some reason.
    if result.inserted_primary_key:
        user_id = result.inserted_primary_key[0]
    else:
        fetched = connection.execute(
            select(user_table.c.id).where(user_table.c.username == username)
        ).first()
        if fetched is not None:
            user_id = fetched[0]

    if user_id is not None:
        target.manager_id = user_id


class Image(db.Model):
    id = db.Column(db.Integer, nullable=False, primary_key=True)
    page_id = db.Column(db.Integer, nullable=False)
    campaign_id = db.Column(
        db.Integer,
        db.ForeignKey('campaign.id'),
        nullable=False
    )
    country_id = db.Column(db.Integer, db.ForeignKey('country.id'))

    def __repr__(self):
        return "Image({}, {}, {})".format(
            self.page_id,
            self.campaign_id,
            self.country_id
        )


class Country(db.Model):
    id = db.Column(db.Integer, nullable=False, primary_key=True)
    name = db.Column(db.Text, nullable=False)
    images = db.relationship('Image', backref='country', lazy=True)

    def __repr__(self):
        return "Country({}, {})".format(
            self.id,
            self.name,
        )


class Suggestion(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True, index=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaign.id'), nullable=False)
    file_name = db.Column(db.String(240), nullable=False)
    depict_item = db.Column(db.String(15), nullable=True)
    update_status = db.Column(db.Integer, default=0)
    google_vision = db.Column(db.Integer, default=0)
    metadata_to_concept = db.Column(db.Integer, default=0)
    metadata_to_concept_confidence = db.Column(db.Float)
    google_vision_confidence = db.Column(db.Float)
    google_vision_submitted = db.Column(db.Integer, default=0)
    metadata_to_concept_submitted = db.Column(db.Integer, default=0)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, nullable=False,
                     default=datetime.now())

    def __repr__(self):
        # This is what is shown when object is printed
        return "Suggestion({}, {}, {}, {}, {}, {}, {})".format(
               self.campaign_id,
               self.file,
               self.depict_item,
               self.google_vision,
               self.metadata_to_concept,
               self.update_status,
               self.user_id)


class DenyListCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True, index=True)
    category_name = db.Column(db.String(250), nullable=False)
    reason = db.Column(db.String(240), nullable=False)

    def __repr__(self):
        # This is what is shown when object is printed
        return "DenyListCategory({}, {})".format(
               self.category_name,
               self.reason)


class DenyList(db.Model):
    id = db.Column(db.Integer, primary_key=True, index=True)
    wikidata_item = db.Column(db.String(15), nullable=False)
    category = db.Column(db.Integer, db.ForeignKey('deny_list_category.id'), nullable=False)

    def __repr__(self):
        # This is what is shown when object is printed
        return "DenyList({}, {})".format(
               self.wikidata_item,
               self.category)
