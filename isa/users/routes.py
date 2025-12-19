import json

import hashlib
import random
import datetime

from flask import Blueprint, flash, redirect, render_template, request, session, url_for, jsonify
from flask_login import current_user, login_user, logout_user
import mwoauth

from isa import app, gettext, db
from isa.main.utils import commit_changes_to_db
from isa.models import User, Campaign, Contribution
from isa.users.forms import LanguageForm
from isa.utils.languages import getLanguages
from isa.users.utils import build_user_pref_lang

users = Blueprint('users', __name__)


@users.route('/api/set-login-url')
def setLoginUrl():
    session['next_url'] = request.args.get('url')
    return "success"


@users.route('/login')
def login():
    """Initiate an OAuth login.

    Call the MediaWiki server to get request secrets and then redirect the
    user to the MediaWiki server to sign the request.
    """
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    else:
        consumer_token = mwoauth.ConsumerToken(
            app.config['CONSUMER_KEY'], app.config['CONSUMER_SECRET'])
        try:
            redirect_string, request_token = mwoauth.initiate(
                app.config['OAUTH_MWURI'], consumer_token)
        except Exception:
            app.logger.exception('mwoauth.initiate failed')
            return redirect(url_for('main.home'))
        else:
            session['request_token'] = dict(zip(
                request_token._fields, request_token))
            if session.get('username'):
                user = User.query.filter_by(username=session.get('username')).first()
                login_user(user)
            return redirect(redirect_string)


@users.route('/oauth-callback')
def oauth_callback():
    """OAuth handshake callback."""
    if 'request_token' not in session:
        flash(gettext('OAuth callback failed. Are cookies disabled?'))
        return redirect(url_for('main.home'))

    consumer_token = mwoauth.ConsumerToken(
        app.config['CONSUMER_KEY'], app.config['CONSUMER_SECRET'])

    try:
        access_token = mwoauth.complete(
            app.config['OAUTH_MWURI'],
            consumer_token,
            mwoauth.RequestToken(**session['request_token']),
            request.query_string)
        identity = mwoauth.identify(
            app.config['OAUTH_MWURI'], consumer_token, access_token)
    except Exception:
        app.logger.exception('OAuth authentication failed')
    else:
        session['access_token'] = dict(zip(
            access_token._fields, access_token))
        session['username'] = identity['username']
        user = User.query.filter_by(username=session.get('username')).first()
        if not user:
            # Create new user and add to db
            user = User(username=session.get('username'), caption_languages='en,fr,,,,')
            db.session.add(user)
            if commit_changes_to_db():
                login_user(user)
        flash(gettext('Welcome %(username)s!', username=session['username']), 'success')
        if session.get('next_url'):
            next_url = session.get('next_url')
            session.pop('next_url', None)
            return redirect(next_url)
        else:
            return redirect(url_for('main.home'))


@users.route('/logout')
def logout():
    """Log the user out by clearing their session."""
    logout_user()
    session.clear()
    flash(gettext('See you next time!'), 'info')
    return redirect(url_for('main.home'))


@users.route('/user-settings', methods=['GET', 'POST'])
def userSettings():
    username = session.get('username', None)
    session_language = session.get('lang', None)
    if not session_language:
        session_language = 'en'
    user_language_set = []
    # This will store the repeating languages
    repeated_language_values = []

    if not username:
        session['next_url'] = request.url
        flash(gettext('Please login to change your language preferences'), 'info')
        return redirect(url_for('main.home'))

    user = User.query.filter_by(username=username).first()
    print("user:", user)
    lang_form = LanguageForm()
    if lang_form.is_submitted():
        caption_language_1 = str(request.form.get('caption_language_select_1'))
        caption_language_2 = str(request.form.get('caption_language_select_2'))
        caption_language_3 = str(request.form.get('caption_language_select_3'))
        caption_language_4 = str(request.form.get('caption_language_select_4'))
        caption_language_5 = str(request.form.get('caption_language_select_5'))
        caption_language_6 = str(request.form.get('caption_language_select_6'))

        # We now check if the user is trying to submit the same language in form

        user_language_set.append(caption_language_1)
        user_language_set.append(caption_language_2)
        user_language_set.append(caption_language_3)
        user_language_set.append(caption_language_4)
        user_language_set.append(caption_language_5)
        user_language_set.append(caption_language_6)

        repeated_languages = []
        for language in user_language_set:
            repeat_count = user_language_set.count(language)
            if repeat_count > 1 and language != '':
                repeated_languages.append(language)
        # we now get all the individual repeating languages
        repeated_languages = list(set(repeated_languages))

        if len(repeated_languages) > 0:
            # In this case at least on language repeats
            # We get the language from the the set of languages and tell the user

            language_options = getLanguages()
            for language_option in language_options:
                if language_option[0] in repeated_languages:
                    repeated_language_values.append(language_option[1])
        if len(repeated_language_values) > 0:
            # In this case there are repeating languages
            repeated_languages_text = ' - '.join(repeated_language_values)
            flash(gettext('Sorry you tried to enter %(rep_languages)s multiple times',
                          rep_languages=repeated_languages_text), 'danger')
            return redirect(url_for('users.userSettings'))
        else:
            user_caption_lang = build_user_pref_lang(caption_language_1, caption_language_2,
                                                     caption_language_3, caption_language_4,
                                                     caption_language_5, caption_language_6)
            # We select the user with username and update their caption_language
            user.caption_languages = user_caption_lang
            user.depicts_language = request.form.get("depicts_language_select")

            # commit failed
            if not commit_changes_to_db():
                flash(gettext('Captions languages could not be set'), 'danger')
            else:
                flash(gettext('Preferred languages set'), 'success')
                # We make sure that the form data does not remain in browser
                return redirect(url_for('users.userSettings'))
    elif request.method == 'GET':
        caption_languages = (user.caption_languages or '').split(',')

    # Ensure exactly 6 items
        while len(caption_languages) < 6:
            caption_languages.append('')
        lang_form.caption_language_select_1.data = str(caption_languages[0])
        lang_form.caption_language_select_2.data = str(caption_languages[1])
        lang_form.caption_language_select_3.data = str(caption_languages[2])
        lang_form.caption_language_select_4.data = str(caption_languages[3])
        lang_form.caption_language_select_5.data = str(caption_languages[4])
        lang_form.caption_language_select_6.data = str(caption_languages[5])
        lang_form.depicts_language_select.data = user.depicts_language
    else:
        flash(gettext('Language settings not available at the moment'), 'info')
    return render_template('users/user_settings.html',
                           title=gettext('%(username)s\'s Settings', username=username),
                           current_user=current_user,
                           session_language=session_language,
                           username=username,
                           lang_form=lang_form)


@users.route('/api/login-test')
def checkUserLogin():
    username = session.get('username', None)
    response_data = {
        'username': username,
        'is_logged_in': bool(username is not None)
    }
    return json.dumps(response_data)


@users.route('/users/<string:username>/campaigns')
def getMyCampaigns(username):
    username = session.get('username', None)
    user = User.query.filter_by(username=username).first()
    session_language = session.get('lang', 'en')
    user_own_campaigns = user.managed_campaigns
    return render_template('users/own_campaigns.html',
                           title=gettext('Campaigns created by %(username)s', username=username),
                           session_language=session_language,
                           user_own_campaigns=user_own_campaigns,
                           username=username)


@users.route('/my-contributions')
def myContributions():
    """Render the My Contributions dashboard for authenticated users."""
    username = session.get('username', None)
    if not username:
        session['next_url'] = request.url
        flash(gettext('Please login to view your contributions'), 'info')
        return redirect(url_for('main.home'))

    session_language = session.get('lang', 'en')
    return render_template('users/my_contributions.html',
                           title=gettext("My Contributions"),
                           current_user=current_user,
                           session_language=session_language,
                           username=username)


@users.route('/api/user/contributions')
def api_user_contributions():
    """Return JSON list of contributions for the currently logged-in user.
    
    Optional query parameters:
    - year: filter by specific year
    - limit: maximum number of contributions to return
    """
    username = session.get('username')
    year = request.args.get('year', type=int)
    limit = request.args.get('limit', type=int)
    
    if not username:
        return jsonify({'error': 'Authentication required'}), 401

    # Show deterministic mock data ONLY for Dev user
    if username == 'Dev':
        seed = int(hashlib.sha256(username.encode('utf-8')).hexdigest()[:8], 16)
        rnd = random.Random(seed)
        try:
            campaign_rows = Campaign.query.all()
            campaigns = [(c.id, c.campaign_name) for c in campaign_rows] or [(None, 'General')]
        except Exception:
            app.logger.exception('Failed to load campaigns, falling back to defaults')
            campaigns = [(None, 'General')]
        countries = ['SE', 'US', 'DE', 'FR', 'GB']
        langs = ['en', 'sv', 'de', 'fr', 'es']
        types = ['caption', 'depicts']

        items = []
        today = datetime.date.today()
        count = 80 + (seed % 50)
        
        # Adjust count and dates based on year filter
        if year:
            # Generate dates only in the specified year
            for i in range(count):
                days_in_year = 365 if year % 4 != 0 else 366  # Simple leap year check
                day_of_year = rnd.randint(0, days_in_year - 1)
                d = datetime.date(year, 1, 1) + datetime.timedelta(days=day_of_year)
                
                cid, cname = campaigns[rnd.randrange(len(campaigns))]
                items.append({
                    'date': d.isoformat(),
                    'campaign': cname,
                    'campaign_id': cid,
                    'file': f'{username}_file_{i}.jpg',
                    'edit_type': types[rnd.randrange(len(types))],
                    'country': countries[rnd.randrange(len(countries))],
                    'lang': langs[rnd.randrange(len(langs))]
                })
        else:
            # Original logic - dates from last 2 years
            for i in range(count):
                days = rnd.randint(0, 730)
                d = today - datetime.timedelta(days=days)
                
                cid, cname = campaigns[rnd.randrange(len(campaigns))]
                items.append({
                    'date': d.isoformat(),
                    'campaign': cname,
                    'campaign_id': cid,
                    'file': f'{username}_file_{i}.jpg',
                    'edit_type': types[rnd.randrange(len(types))],
                    'country': countries[rnd.randrange(len(countries))],
                    'lang': langs[rnd.randrange(len(langs))]
                })
        
        # Apply limit if specified
        if limit and limit > 0:
            items = items[:limit]
            
        return jsonify({'data': items})

    # For all other users, fetch real contributions from DB
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'data': []})

    try:
        # Build query
        query = (db.session.query(Contribution, Campaign.id, Campaign.campaign_name)
            .join(Campaign, Contribution.campaign_id == Campaign.id)
            .filter(Contribution.user_id == user.id))
        
        # Apply year filter if specified
        if year:
            start_date = datetime.date(year, 1, 1)
            end_date = datetime.date(year, 12, 31)
            query = query.filter(
                Contribution.date >= start_date,
                Contribution.date <= end_date
            )
        
        # Order and limit
        query = query.order_by(Contribution.date.desc())
        
        if limit and limit > 0:
            rows = query.limit(limit).all()
        else:
            rows = query.all()
            
    except Exception:
        app.logger.exception('Failed to load user contributions for %s', username)
        return jsonify({'error': 'Failed to load contributions'}), 500

    items = []
    for contrib, campaign_id, campaign_name in rows:
        # contrib.date is a Date, convert to ISO string
        date_str = contrib.date.isoformat() if hasattr(contrib.date, 'isoformat') else str(contrib.date)
        items.append({
            'date': date_str,
            'campaign': campaign_name or 'General',
            'campaign_id': campaign_id,
            'file': contrib.file,
            'edit_type': contrib.edit_type,
            'country': contrib.country or '',
            'lang': contrib.caption_language or ''
        })

    return jsonify({'data': items})

@users.route('/year-in-review')
def year_in_review():
    """Render the Year in Review celebration page."""
    username = session.get('username', None)
    if not username:
        session['next_url'] = request.url
        flash(gettext('Please login to view your Year in Review'), 'info')
        return redirect(url_for('main.home'))

    session_language = session.get('lang', 'en')
    current_year = datetime.date.today().year
    
    return render_template('users/year_in_review.html',
                           title=gettext("Year in Review"),
                           current_user=current_user,
                           session_language=session_language,
                           username=username,
                           current_year=current_year)


@users.route('/api/user/year-stats')
def api_user_year_stats():
    """Return JSON statistics for the current user for a specific year."""
    username = session.get('username')
    year = request.args.get('year', type=int)
    
    if not username:
        return jsonify({'error': 'Authentication required'}), 401
    
    if not year:
        year = datetime.date.today().year

    # For the Dev user, mirror the deterministic mock data used by
    # /api/user/contributions so that Year in Review shows meaningful stats
    # even when there are no real DB contributions.
    if username == 'Dev':
        seed = int(hashlib.sha256(username.encode('utf-8')).hexdigest()[:8], 16)
        rnd = random.Random(seed)

        try:
            campaign_rows = Campaign.query.all()
            campaigns = [(c.id, c.campaign_name) for c in campaign_rows] or [(None, 'General')]
        except Exception:
            app.logger.exception('Failed to load campaigns for Dev year stats, falling back to defaults')
            campaigns = [(None, 'General')]

        countries = ['SE', 'US', 'DE', 'FR', 'GB']
        langs = ['en', 'sv', 'de', 'fr', 'es']
        types = ['caption', 'depicts']

        items = []
        count = 80 + (seed % 50)

        # Generate dates only inside the requested year
        days_in_year = 365 if year % 4 != 0 else 366
        for i in range(count):
            day_of_year = rnd.randint(0, days_in_year - 1)
            d = datetime.date(year, 1, 1) + datetime.timedelta(days=day_of_year)

            _cid, cname = campaigns[rnd.randrange(len(campaigns))]
            items.append({
                'date': d.isoformat(),
                'campaign': cname,
                'file': f'{username}_file_{i}.jpg',
                'edit_type': types[rnd.randrange(len(types))],
                'country': countries[rnd.randrange(len(countries))],
                'lang': langs[rnd.randrange(len(langs))]
            })

        # Aggregate statistics from the generated items
        total_edits = len(items)
        depicts_edits = sum(1 for it in items if it['edit_type'] == 'depicts')
        caption_edits = sum(1 for it in items if it['edit_type'] == 'caption')

        campaigns_set = set(it['campaign'] for it in items if it.get('campaign'))
        languages_set = set(it['lang'] for it in items if it.get('lang'))

        campaigns_details = {}
        for it in items:
            name = it.get('campaign') or 'General'
            campaigns_details[name] = campaigns_details.get(name, 0) + 1

        campaigns_count = len(campaigns_set)
        languages_count = len(languages_set)

        top_campaigns = sorted(
            campaigns_details.items(),
            key=lambda x: x[1],
            reverse=True
        )[:6]

        return jsonify({
            'success': True,
            'year': year,
            'stats': {
                'total_edits': total_edits,
                'depicts_edits': depicts_edits,
                'caption_edits': caption_edits,
                'campaigns_count': campaigns_count,
                'languages_count': languages_count
            },
            'top_campaigns': [
                {
                    'name': name,
                    'edits': count,
                    'year': year
                }
                for name, count in top_campaigns
            ]
        })
    
    # Get user
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    try:
        # Calculate start and end dates for the year
        start_date = datetime.date(year, 1, 1)
        end_date = datetime.date(year, 12, 31)
        
        # Query contributions for the year
        contributions = (db.session.query(Contribution, Campaign.campaign_name)
            .join(Campaign, Contribution.campaign_id == Campaign.id)
            .filter(
                Contribution.user_id == user.id,
                Contribution.date >= start_date,
                Contribution.date <= end_date
            )
            .all())
        
        # Calculate statistics
        stats = {
            'total_edits': len(contributions),
            'depicts_edits': 0,
            'caption_edits': 0,
            'campaigns': set(),
            'languages': set(),
            'campaigns_details': {}
        }
        
        for contrib, campaign_name in contributions:
            # Count by edit type
            if contrib.edit_type == 'depicts':
                stats['depicts_edits'] += 1
            elif contrib.edit_type == 'caption':
                stats['caption_edits'] += 1
            
            # Track campaigns
            if campaign_name:
                stats['campaigns'].add(campaign_name)
                # Count edits per campaign
                if campaign_name not in stats['campaigns_details']:
                    stats['campaigns_details'][campaign_name] = 0
                stats['campaigns_details'][campaign_name] += 1
            
            # Track languages
            if contrib.caption_language:
                stats['languages'].add(contrib.caption_language)
        
        # Convert sets to counts
        stats['campaigns_count'] = len(stats['campaigns'])
        stats['languages_count'] = len(stats['languages'])
        
        # Get top campaigns (sorted by edit count)
        top_campaigns = sorted(
            stats['campaigns_details'].items(),
            key=lambda x: x[1],
            reverse=True
        )[:6]  # Top 6 campaigns
        
        return jsonify({
            'success': True,
            'year': year,
            'stats': {
                'total_edits': stats['total_edits'],
                'depicts_edits': stats['depicts_edits'],
                'caption_edits': stats['caption_edits'],
                'campaigns_count': stats['campaigns_count'],
                'languages_count': stats['languages_count']
            },
            'top_campaigns': [
                {
                    'name': name,
                    'edits': count,
                    'year': year
                }
                for name, count in top_campaigns
            ]
        })
        
    except Exception as e:
        app.logger.exception(f'Failed to calculate year stats for {username}: {str(e)}')
        return jsonify({
            'success': False,
            'error': 'Failed to calculate year stats'
        }), 500


@users.route('/api/user/top-campaigns')
def api_user_top_campaigns():
    """Return top campaigns for the current user."""
    username = session.get('username')
    limit = request.args.get('limit', 6, type=int)
    
    if not username:
        return jsonify({'error': 'Authentication required'}), 401
    
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    try:
        # Query campaigns with contribution counts
        campaigns = (db.session.query(
                Campaign.campaign_name,
                db.func.count(Contribution.id).label('edit_count')
            )
            .join(Contribution, Campaign.id == Contribution.campaign_id)
            .filter(Contribution.user_id == user.id)
            .group_by(Campaign.campaign_name)
            .order_by(db.desc('edit_count'))
            .limit(limit)
            .all())
        
        campaign_list = []
        for campaign_name, edit_count in campaigns:
            campaign_list.append({
                'name': campaign_name,
                'edits': edit_count,
                'html': f'<strong>{campaign_name}</strong>'
            })

        return jsonify({
            'success': True,
            'campaigns': campaign_list
        })
        
    except Exception as e:
        app.logger.exception(f'Failed to fetch top campaigns for {username}: {str(e)}')
        return jsonify({
            'success': False,
            'error': 'Failed to fetch top campaigns'
        }), 500
        
        return jsonify({
            'success': True,
            'campaigns': mock_campaigns[:limit]
        })