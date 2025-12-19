from datetime import datetime
import glob
import json
import os

import requests
from flask import (make_response, render_template, redirect, url_for, flash, request,
                   session, Blueprint, send_file, jsonify, abort)
from flask_login import current_user
from markupsafe import Markup, escape
from sqlalchemy import func, or_
from sqlalchemy.exc import SQLAlchemyError

from isa import app, db, gettext
from isa.campaigns.forms import CampaignForm
from isa.campaigns.utils import (convert_latin_to_english, get_table_stats, compute_campaign_status,
                                 create_campaign_country_stats_csv, create_campaign_contributor_stats_csv,
                                 create_campaign_all_stats_csv, get_all_camapaign_stats_data,
                                 make_edit_api_call, generate_csrf_token,
                                 get_stats_data_points)
from isa.campaigns import image_updater
from isa.main.utils import commit_changes_to_db, manage_session
from isa.models import Campaign, Contribution, Country, Image, User, Suggestion
from isa.users.utils import (get_user_language_preferences, get_current_user_images_improved)


campaigns = Blueprint('campaigns', __name__)


@manage_session
@campaigns.route('/campaigns')
def getCampaigns():
    username = session.get('username', None)
    session_language = session.get('lang', None)
    if not session_language:
        session_language = 'en'
    session['next_url'] = request.url
    return render_template('campaign/campaigns.html',
                           title=gettext('Campaigns'),
                           username=username,
                           session_language=session_language,
                           today_date=datetime.date(datetime.utcnow()),
                           datetime=datetime,
                           current_user=current_user)


@campaigns.route('/api/campaigns', methods=['GET', 'POST'])
def getCampaignsPaginated():
    """DataTables server-side endpoint for the Campaigns listing."""

    def _int_param(name, default=None, min_value=None, max_value=None):
        raw = request.values.get(name, None)
        if raw is None or raw == '':
            return default
        try:
            value = int(raw)
        except (TypeError, ValueError):
            return default
        if min_value is not None and value < min_value:
            return default
        if max_value is not None and value > max_value:
            return default
        return value

    draw = _int_param('draw', default=0, min_value=0)

    # Support both DataTables (start/length) and a simpler page/per_page API.
    page = _int_param('page', default=None, min_value=1)
    per_page = _int_param('per_page', default=None, min_value=1, max_value=100)

    if page is not None or per_page is not None:
        length = per_page if per_page is not None else 30
        start = ((page or 1) - 1) * length
    else:
        start = _int_param('start', default=0, min_value=0)
        length = _int_param('length', default=30, min_value=1, max_value=100)

    # Compact params supported to avoid massive query strings.
    # DataTables default params are still supported for backwards compatibility.
    search_value = (request.values.get('search_value') or request.values.get('search[value]') or '').strip()

    show_archived_raw = (request.values.get('show_archived') or '').strip()
    show_archived = show_archived_raw in ('1', 'true', 'True', 'yes', 'on')

    show_archived_provided = request.values.get('show_archived') is not None

    # Archived toggle is implemented as a column-search on hidden column index 8
    # (used by older clients). When show_archived is explicitly provided, it takes precedence.
    status_search_value = (request.values.get('columns[8][search][value]', '') or '').strip()

    # Order handling (best-effort; ignore unknown columns)
    order_col_idx = _int_param('order_col', default=None, min_value=0)
    if order_col_idx is None:
        order_col_idx = _int_param('order[0][column]', default=None, min_value=0)

    order_dir = (request.values.get('order_dir') or request.values.get('order[0][dir]') or 'asc').lower()
    order_dir = 'desc' if order_dir == 'desc' else 'asc'

    today = datetime.utcnow().date()

    query = Campaign.query

    # Hide archived (closed) campaigns by default.
    # New clients send show_archived explicitly; older clients used a column-search on hidden col 8.
    if show_archived_provided:
        if not show_archived:
            query = query.filter(or_(Campaign.end_date.is_(None), Campaign.end_date >= today))
    else:
        if status_search_value == '1':
            query = query.filter(or_(Campaign.end_date.is_(None), Campaign.end_date >= today))

    # DataTables expects recordsTotal to reflect the current base dataset (e.g., after applying
    # user-controlled filters like show_archived) and recordsFiltered to reflect additional
    # filtering from the global search box.
    records_total = query.count()

    if search_value:
        like_value = f"%{search_value}%"
        query = query.filter(or_(
            Campaign.campaign_name.ilike(like_value),
            Campaign.short_description.ilike(like_value),
            Campaign.long_description.ilike(like_value),
        ))

    records_filtered = query.count()

    # Map DataTables column index -> SQLAlchemy order-by
    order_map = {
        0: Campaign.campaign_name,
        1: Campaign.campaign_images,
        2: Campaign.campaign_participants,
        3: Campaign.campaign_contributions,
        4: Campaign.start_date,
        5: Campaign.end_date,
    }
    order_col = order_map.get(order_col_idx, Campaign.start_date)
    if order_dir == 'desc':
        query = query.order_by(order_col.desc(), Campaign.id.desc())
    else:
        query = query.order_by(order_col.asc(), Campaign.id.asc())

    campaigns_page = query.offset(start).limit(length).all()
    page_number = (start // length) + 1 if length else 1

    data = []
    for campaign in campaigns_page:
        campaign_name = escape(campaign.campaign_name or '')
        short_desc = escape(campaign.short_description or '')
        long_desc = escape(campaign.long_description or '')

        # Status computation (matches template logic)
        is_archived = bool(campaign.end_date and campaign.end_date < today)
        is_upcoming = bool(campaign.start_date and campaign.start_date >= today)

        if is_archived:
            # Archived: red badge
            status_html = Markup(
                '<span class="badge bg-danger bg-opacity-10 text-danger border border-danger '
                'border-opacity-25 rounded-pill px-3 py-1">'
                '<i class="fas fa-archive me-1"></i>%s</span>'
            ) % escape(gettext('Archived'))
            status_flag = 0
        elif is_upcoming:
            # Upcoming: neutral/amber badge
            status_html = Markup(
                '<span class="badge bg-warning bg-opacity-10 text-warning border border-warning '
                'border-opacity-25 rounded-pill px-3 py-1">'
                '<i class="fas fa-clock me-1"></i>%s</span>'
            ) % escape(gettext('Upcoming'))
            status_flag = 1
        else:
            # Active: green badge
            status_html = Markup(
                '<span class="badge bg-success bg-opacity-10 text-success border border-success '
                'border-opacity-25 rounded-pill px-3 py-1">'
                '<i class="fas fa-play-circle me-1"></i>%s</span>'
            ) % escape(gettext('Active'))
            status_flag = 1

        end_date_html = (
            Markup('<span class="text-muted">%s</span>') % escape(gettext('Ongoing'))
            if campaign.end_date is None
            else escape(campaign.end_date.strftime('%Y-%m-%d'))
        )

        # Images column (mirrors template macro)
        images_html = Markup('%s') % escape(str(campaign.campaign_images or 0))
        if campaign.update_status == 1:
            images_html += Markup(
                '<button type="button" class="btn btn-link py-0" data-container="body" '
                'title="%s" data-toggle="popover" data-trigger="focus" data-placement="right" '
                'data-content="%s">'
                '<i class="fa fa-clock"></i></button>'
            ) % (
                escape(gettext('Updating images')),
                escape(
                    gettext('The images for this campaign are being updated.') + ' ' +
                    gettext('More images will be added.') + ' ' +
                    gettext('You can still participate in the campaign.')
                ),
            )
        elif campaign.update_status == 2:
            images_html += Markup(
                '<button type="button" class="btn btn-link py-0" data-container="body" '
                'title="%s" data-toggle="popover" data-trigger="focus" data-placement="right" '
                'data-content="%s">'
                '<i class="fa fa-exclamation-circle"></i></button>'
            ) % (
                escape(gettext('Failed to update images')),
                escape(
                    gettext('There was an error while updating the images for this campaign.') + ' ' +
                    gettext('Some images will be missing.') + ' ' +
                    gettext('You can still participate in the campaign.') + ' ' +
                    gettext('The campaign manager can retry by updating the campaign.')
                ),
            )

        campaign_html = Markup(
            '<div class="d-flex flex-column">'
            '<strong class="mb-1">%s</strong>'
            '<span class="small text-muted campaign-description">%s</span>'
            '</div>'
        ) % (campaign_name, short_desc)

        data.append({
            'href': url_for('campaigns.getCampaignById', id=campaign.id),
            'campaign_html': campaign_html,
            'images_html': images_html,
            'participants': int(campaign.campaign_participants or 0),
            'contributions': int(campaign.campaign_contributions or 0),
            'start_date': campaign.start_date.strftime('%Y-%m-%d') if campaign.start_date else '',
            'end_date_html': end_date_html,
            'status_html': status_html,
            'actions_html': Markup(
                '<a href="%s" class="btn btn-sm btn-outline-primary rounded-1 px-3 py-1">%s</a>'
            ) % (escape(url_for('campaigns.getCampaignById', id=campaign.id)), escape(gettext('View'))),
            'status_flag': status_flag,
            'long_description': long_desc,
        })

    has_more = (start + len(campaigns_page)) < records_filtered
    return jsonify({
        'draw': draw,
        'recordsTotal': records_total,
        'recordsFiltered': records_filtered,
        'page': page_number,
        'per_page': length,
        'has_more': has_more,
        'data': data,
    })


@campaigns.route('/campaigns/<int:id>')
def getCampaignById(id):

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    # We get the current user's user_name
    username = session.get('username', None)
    session_language = session.get('lang', None)
    if not session_language:
        session_language = 'en'
    campaign = Campaign.query.get(id)
    if not campaign:
        flash(gettext('Campaign with id %(id)s does not exist', id=id), 'info')
        return redirect(url_for('campaigns.getCampaigns'))

    # We get all the contributions from the ddatabase
    all_contributions = Contribution.query.filter_by(campaign_id=campaign.id).all()
    # contributions for campaign
    campaign_contributions = 0
    # Editor for a particular campaign
    campaign_editors = 0
    # We now get the contributor count for this campaign
    for contrib in all_contributions:
        if (contrib.campaign_id == campaign.id):
            campaign_contributions += 1

    try:
        campaign_table_stats = get_table_stats(id, username, page, per_page)
    except SQLAlchemyError:
        app.logger.exception('Database error while loading campaign table for %s', id)
        flash(gettext('Database error while loading campaign statistics. Please try again later.'), 'danger')
        return redirect(url_for('campaigns.getCampaigns'))
    except Exception:
        app.logger.exception('Unexpected error while loading campaign table for %s', id)
        flash(gettext('An internal error occurred while loading campaign statistics'), 'danger')
        return redirect(url_for('campaigns.getCampaigns'))

    # Validate returned data to avoid raw 500s when downstream code expects a dict
    if not campaign_table_stats or not isinstance(campaign_table_stats, dict):
        app.logger.error('Invalid campaign_table_stats returned for %s: %r', id, campaign_table_stats)
        flash(gettext('Unable to load campaign statistics.'), 'info')
        return redirect(url_for('campaigns.getCampaigns'))
    # Delete the files in the campaign directory
    stats_path = os.getcwd() + '/campaign_stats_files/' + str(campaign.id)
    files = glob.glob(stats_path + '/*')
    if len(files) > 0:
        for f in files:
            os.remove(f)

    # We create the campaign stats directory if it does not exist
    if not os.path.exists(stats_path):
        os.makedirs(stats_path)

    # We build the campaign statistucs file here with the contributor stats
    # 1 - country contribution file

    campaign_name = campaign.campaign_name
    stats_file_directory = stats_path
    country_fields = ['rank', 'country', 'images_improved']
    country_stats_data = campaign_table_stats['all_campaign_country_statistics_data']

    country_csv_file = create_campaign_country_stats_csv(stats_file_directory, campaign_name,
                                                         country_fields, country_stats_data)

    # 2 - contributors file
    contributor_fields = ['rank', 'username', 'images_improved']
    contributor_stats_data = campaign_table_stats['all_contributors_data']

    current_user_images_improved = get_current_user_images_improved(contributor_stats_data, username)

    contributor_csv_file = create_campaign_contributor_stats_csv(stats_file_directory,
                                                                 campaign_name,
                                                                 contributor_fields,
                                                                 contributor_stats_data)
    campaign.campaign_participants = campaign_table_stats['campaign_editors']
    campaign.campaign_contributions = campaign_contributions
    if commit_changes_to_db():
        print('Campaign info updated successfully!')
    session['next_url'] = request.url
    campaign_image = ('https://commons.wikimedia.org/wiki/Special:FilePath/' + campaign.campaign_image
                      if campaign.campaign_image != ''
                      else None)
    countries = Country.query.join(Image).filter(Image.campaign_id == campaign.id).all()
    country_names = sorted([c.name for c in countries])
    return (render_template('campaign/campaign.html', title=gettext('Campaign - %(campaign_name)s',
                                                                    campaign_name=campaign.campaign_name),
                            campaign_name=campaign.campaign_name,
                            campaign=campaign,
                            manager=campaign.manager,
                            username=username,
                            campaign_image=campaign_image,
                            session_language=session_language,
                            campaign_editors=campaign_editors,
                            campaign_contributions=campaign_contributions,
                            current_user=current_user,
                            is_wiki_loves_campaign=campaign.campaign_type,
                            campaign_table_pagination_data=campaign_table_stats['page_info'],
                            all_contributors_data=campaign_table_stats['all_contributors_data'],
                            current_user_rank=campaign_table_stats['current_user_rank'],
                            all_campaign_country_statistics_data=campaign_table_stats['all_campaign_country_statistics_data'],
                            current_user_images_improved=current_user_images_improved,
                            contributor_csv_file=contributor_csv_file,
                            country_csv_file=country_csv_file,
                            countries=country_names,
                            isa_superusers=app.config.get('ISA_SUPERUSERS', [])
                            ))


@campaigns.route('/campaigns/<int:id>/table')
def getCampaignTableData(id):
    # Validate campaign existence and request parameters, then return table stats
    try:
        # Ensure campaign exists
        campaign = Campaign.query.get(id)
        if not campaign:
            return make_response(jsonify({'error': gettext('Campaign with id %(id)s does not exist', id=id)}), 404)

        # Parse raw query parameters so we can return 400 on malformed values
        page_raw = request.args.get('page', None)
        per_page_raw = request.args.get('per_page', None)

        # page is optional; per_page defaults to 30
        try:
            page = int(page_raw) if page_raw is not None else None
        except (TypeError, ValueError):
            return make_response(jsonify({'error': gettext('Invalid "page" parameter')}), 400)

        try:
            per_page = int(per_page_raw) if per_page_raw is not None else 30
        except (TypeError, ValueError):
            return make_response(jsonify({'error': gettext('Invalid "per_page" parameter')}), 400)

        # Validate numeric ranges
        if page is not None and page <= 0:
            return make_response(jsonify({'error': gettext('Invalid "page" parameter')}), 400)
        if per_page <= 0:
            return make_response(jsonify({'error': gettext('Invalid "per_page" parameter')}), 400)

        username = session.get('username', None)
        campaign_table_stats = get_table_stats(id, username, page, per_page)
        return jsonify(campaign_table_stats)
    except Exception:
        app.logger.exception('Unexpected error while loading campaign table for %s', id)
        return make_response(jsonify({'error': gettext('An internal error occurred')}), 500)

@campaigns.route('/campaigns/<int:id>/stats')
def getCampaignStatsById(id):
    """Display the statistics page for a specific campaign."""
    # Basic session/context data used by the base layout/header
    username = session.get('username', None)
    session_language = session.get('lang', None)
    if not session_language:
        session_language = 'en'

    session['next_url'] = request.url

    campaign = Campaign.query.get_or_404(id)
    base_query = Contribution.query.filter_by(campaign_id=id)
    total_contributions = base_query.count()

    # 1. Contributions Over Time (Date-wise)
    datewise_data_query = db.session.query(
        Contribution.date,
        func.count(Contribution.id).label('count')
    ).filter_by(campaign_id=id).group_by(Contribution.date).order_by(Contribution.date).all()
    datewise_data = [{'date': r.date.strftime('%Y-%m-%d'), 'count': r.count} for r in datewise_data_query]

    # 2. Top 10 Contributors
    top_contributors_query = db.session.query(
        User.username,
        func.count(Contribution.id).label('count')
    ).join(User, User.id == Contribution.user_id).filter(Contribution.campaign_id == id).group_by(User.username).order_by(func.count(Contribution.id).desc()).limit(5).all()
    top_contributors = [{'username': r.username, 'count': r.count} for r in top_contributors_query]

    # 3. Language Distribution
    language_stats_query = db.session.query(
        Contribution.caption_language.label('language'),
        func.count(Contribution.id).label('count')
    ).filter(
        Contribution.campaign_id == id,
        Contribution.caption_language.isnot(None),
        Contribution.caption_language != ''
    ).group_by('language').order_by(func.count(Contribution.id).desc()).all()
    language_stats = [{'language': r.language, 'count': r.count} for r in language_stats_query]

    # 4. Country Distribution
    country_distribution_query = db.session.query(
        Contribution.country,
        func.count(Contribution.id).label('count')
    ).filter(
        Contribution.campaign_id == id,
        Contribution.country.isnot(None),
        Contribution.country != ''
    ).group_by(Contribution.country).order_by(func.count(Contribution.id).desc()).all()
    country_distribution = [{'country': r.country, 'count': r.count} for r in country_distribution_query]

    # 5. Contribution Types
    contribution_types_query = db.session.query(
        Contribution.edit_type,
        func.count(Contribution.id).label('count')
    ).filter(
        Contribution.campaign_id == id,
        Contribution.edit_type.isnot(None),
        Contribution.edit_type != ''
    ).group_by(Contribution.edit_type).order_by(func.count(Contribution.id).desc()).all()
    contribution_types = [{'type': r.edit_type, 'count': r.count} for r in contribution_types_query]

    # Render the template with the correctly formatted data
    return render_template(
        'campaign/campaign_stats.html',
        title=gettext('Campaign stats - %(campaign_name)s',
                      campaign_name=campaign.campaign_name),
        campaign=campaign,
        total_contributions=total_contributions,
        datewise_data=datewise_data,
        top_contributors=top_contributors,
        language_stats=language_stats,
        country_distribution=country_distribution,
        contribution_types=contribution_types,
        session_language=session_language,
        username=username,
        current_user=current_user,
    )

@campaigns.route('/api/campaigns/<int:campaign_id>/stats_by_date')
def get_stats_by_date(campaign_id):
    """
    API endpoint to deliver all campaign stats within a specific date range.
    """
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    # Verify campaign exists
    campaign = Campaign.query.get(campaign_id)
    if not campaign:
        return make_response(jsonify({'error': gettext('Campaign with id %(id)s does not exist', id=campaign_id)}), 404)

    # Parse and validate dates
    try:
        start_date = None
        end_date = None
        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        # Ensure start_date is not after end_date
        if start_date and end_date and start_date > end_date:
            return make_response(jsonify({'error': gettext('Invalid date range; start_date must be on or before end_date')}), 400)
    except ValueError:
        return make_response(jsonify({'error': gettext('Invalid date format; expected YYYY-MM-DD')}), 400)

    try:
        # Base filter list to be applied to every query
        filters = [Contribution.campaign_id == campaign_id]
        if start_date:
            filters.append(Contribution.date >= start_date)
        if end_date:
            filters.append(Contribution.date <= end_date)

        # Total contributions in the date range
        total_contributions = db.session.query(func.count(Contribution.id)).filter(*filters).scalar()

        datewise_data_query = db.session.query(
            Contribution.date,
            func.count(Contribution.id).label('count')
        ).filter(*filters).group_by(Contribution.date).order_by(Contribution.date).all()
        datewise_data = [{'date': r.date.strftime('%Y-%m-%d'), 'count': r.count} for r in datewise_data_query]
        
        # Top 5 contributors in the date range
        top_contributors_query = db.session.query(
            User.username,
            func.count(Contribution.id).label('count')
        ).join(Contribution, User.id == Contribution.user_id).filter(*filters).group_by(User.username).order_by(func.count(Contribution.id).desc()).limit(5).all()
        top_contributors = [{'username': r.username, 'count': r.count} for r in top_contributors_query]

        # Language stats in the date range
        language_stats_query = db.session.query(
            Contribution.caption_language.label('language'),
            func.count(Contribution.id).label('count')
        ).filter(Contribution.caption_language.isnot(None), Contribution.caption_language != '', *filters).group_by('language').order_by(func.count(Contribution.id).desc()).all()
        language_stats = [{'language': r.language, 'count': r.count} for r in language_stats_query]

        # Country distribution in the date range
        country_distribution_query = db.session.query(
            Contribution.country,
            func.count(Contribution.id).label('count')
        ).filter(Contribution.country.isnot(None), Contribution.country != '', *filters).group_by(Contribution.country).order_by(func.count(Contribution.id).desc()).all()
        country_distribution = [{'country': r.country, 'count': r.count} for r in country_distribution_query]

        # Contribution types in the date range
        contribution_types_query = db.session.query(
            Contribution.edit_type,
            func.count(Contribution.id).label('count')
        ).filter(Contribution.edit_type.isnot(None), Contribution.edit_type != '', *filters).group_by(Contribution.edit_type).order_by(func.count(Contribution.id).desc()).all()
        contribution_types = [{'type': r.edit_type, 'count': r.count} for r in contribution_types_query]

        return jsonify({
            'total_contributions': total_contributions,
            'datewise_data': datewise_data,
            'top_contributors': top_contributors,
            'language_stats': language_stats,
            'country_distribution': country_distribution,
            'contribution_types': contribution_types
        })
    except Exception:
        app.logger.exception('Unexpected error while generating stats for campaign %s', campaign_id)
        return make_response(jsonify({'error': gettext('An internal error occurred')}), 500)

@campaigns.route('/campaigns/create', methods=['GET', 'POST'])
def CreateCampaign():
    # We get the current user's user_name
    username = session.get('username', None)
    session_language = session.get('lang', None)
    if not session_language:
        session_language = 'en'
    form = CampaignForm()
    if not username:
        session['next_url'] = request.url
        flash(gettext('You need to log in to create a campaign'), 'info')
        return redirect(url_for('campaigns.getCampaigns'))
    else:
        if form.is_submitted():
            form_categories = ",".join(request.form.getlist('categories'))
            # here we create a campaign
            # We add the campaign information to the database
            campaign_end_date = None
            if form.end_date.data == '':
                campaign_end_date = None
            else:
                campaign_end_date = datetime.strptime(form.end_date.data, '%Y-%m-%d')
            user = User.query.filter_by(username=username).first()
            campaign = Campaign(
                campaign_name=form.campaign_name.data,
                categories=form_categories,
                start_date=datetime.strptime(form.start_date.data, '%Y-%m-%d'),
                manager=user,
                end_date=campaign_end_date,
                status=compute_campaign_status(campaign_end_date),
                short_description=form.short_description.data,
                long_description=form.long_description.data,
                creation_date=datetime.now().date(),
                depicts_metadata=form.depicts_metadata.data,
                campaign_image=form.campaign_image.data,
                captions_metadata=form.captions_metadata.data,
                campaign_type=form.campaign_type.data)
            db.session.add(campaign)
            # commit failed
            if not commit_changes_to_db():
                flash(gettext('Sorry, %(campaign_name)s could not be created',
                              campaign_name=form.campaign_name.data), 'info')
            else:
                image_updater.update_in_task(campaign.id)
                campaign_stats_path = str(campaign.id)
                stats_path = os.getcwd() + '/campaign_stats_files/' + campaign_stats_path
                if not os.path.exists(stats_path):
                    os.makedirs(stats_path)
                flash(gettext('%(campaign_name)s campaign created!',
                              campaign_name=form.campaign_name.data), 'success')
                return redirect(url_for('campaigns.getCampaignById', id=campaign.id))
        return render_template('campaign/campaign-form.html', title=gettext('Create a campaign'),
                               form=form, datetime=datetime,
                               username=username,
                               session_language=session_language,
                               current_user=current_user)


@campaigns.route('/campaigns/<int:id>/participate')
def contributeToCampaign(id):
    # We select the campaign whose id comes into the route
    campaign = Campaign.query.filter_by(id=id).first()

    # We get current user in sessions's username
    username = session.get('username', None)
    session_language = session.get('lang', None)
    if not session_language:
        session_language = 'en'
    session['next_url'] = request.url
    return render_template('campaign/campaign_entry.html',
                           is_update=False,
                           title=gettext('%(campaign_name)s - Contribute',
                                         campaign_name=campaign.campaign_name),
                           id=id,
                           session_language=session_language,
                           caption_languages=get_user_language_preferences(username),
                           campaign=campaign,
                           username=username,
                           current_user=current_user)


@campaigns.route('/campaigns/<int:id>/update', methods=['GET', 'POST'])
def updateCampaign(id):
    # We get the current user's user_name
    username = session.get('username', None)
    session_language = session.get('lang', None)
    if not session_language:
        session_language = 'en'
    form = CampaignForm()
    if not username:
        flash(gettext('You need to log in to update a campaign'), 'info')
        return redirect(url_for('campaigns.getCampaigns'))

    user = User.query.filter_by(username=username).first()
    # when the form is submitted, we update the campaign
    # TODO: Check if campaign is closed so that it cannot be edited again
    # This is a potential issue/Managerial
    if form.is_submitted():
        campaign_end_date = None
        if form.end_date.data == '':
            campaign_end_date = None
        else:
            campaign_end_date = datetime.strptime(form.end_date.data, '%Y-%m-%d')
        campaign = Campaign.query.get(id)
        campaign.campaign_name = form.campaign_name.data
        # Only update the campaign manager if the current user is the existing
        # manager (or if the campaign has no manager). Do NOT overwrite the
        # manager when a superuser edits the campaign.
        if campaign.manager is None or campaign.manager.username == username:
            campaign.manager = user
        campaign.short_description = form.short_description.data
        campaign.long_description = form.long_description.data
        campaign.depicts_metadata = form.depicts_metadata.data
        campaign.captions_metadata = form.captions_metadata.data
        campaign.categories = form.categories.data
        campaign.start_date = datetime.strptime(form.start_date.data, '%Y-%m-%d')
        campaign.campaign_image = form.campaign_image.data
        campaign.campaign_type = form.campaign_type.data
        campaign.end_date = campaign_end_date
        if not commit_changes_to_db():
            flash(gettext('Campaign update failed. Please try later!'), 'danger')
        else:
            if form.update_images.data:
                image_updater.update_in_task(id)
            flash(gettext('Update succesfull!'), 'success')
            return redirect(url_for('campaigns.getCampaignById', id=id))

    # User requests to edit so we update the form with Campaign details
    elif request.method == 'GET':
        # we get the campaign data to place in form fields
        campaign = Campaign.query.filter_by(id=id).first()

        isa_superusers = app.config.get('ISA_SUPERUSERS', [])
        if campaign.manager != user and username not in isa_superusers:
            flash(gettext('You cannot update this campaign. Contact the manager, User:%(username)s.',
                          username=campaign.manager.username), 'info')
            return redirect(url_for('campaigns.getCampaignById', id=id))

        form.campaign_name.data = campaign.campaign_name
        form.short_description.data = campaign.short_description
        form.long_description.data = campaign.long_description
        form.categories.data = campaign.categories
        form.campaign_images.data = campaign.campaign_images
        form.start_date.data = campaign.start_date
        form.depicts_metadata.data = campaign.depicts_metadata
        form.campaign_image.data = campaign.campaign_image
        form.captions_metadata.data = campaign.captions_metadata
        form.campaign_type.data = campaign.campaign_type
        form.end_date.data = campaign.end_date
    else:
        flash(gettext('Booo! %(campaign_name)s could not be updated!',
                      campaign_name=form.campaign_name.data), 'danger')
    session['next_url'] = request.url
    return render_template('campaign/campaign-form.html',
                           is_update=True,
                           title=gettext('%(campaign_name)s - Update',
                                         campaign_name=campaign.campaign_name),
                           campaign=campaign,
                           form=form,
                           session_language=session_language,
                           current_user=current_user,
                           username=username)


@campaigns.route('/api/get-campaign-categories')
def getCampaignCategories():
    # we get the campaign_id from the route request
    campaign_id = request.args.get('campaign')

    # Validate input
    if not campaign_id:
        return make_response(jsonify({'error': gettext('Missing "campaign" parameter')}), 400)

    try:
        # Ensure campaign exists
        campaign = Campaign.query.filter_by(id=campaign_id).first()
        if not campaign:
            return make_response(jsonify({'error': gettext('Campaign with id %(id)s does not exist', id=campaign_id)}), 404)

        # Return categories as JSON
        return jsonify({'categories': campaign.categories})
    except Exception:
        app.logger.exception('Error while retrieving campaign categories for id %s', campaign_id)
        return make_response(jsonify({'error': gettext('An internal error occurred')}), 500)


@campaigns.route('/api/get-campaign-graph-stats-data')
def getCampaignGraphStatsData():
    # we get the campaign_id from the route request
    page = request.args.get('page', None, type=int)
    per_page = request.args.get('per_page', 30, type=int)
    campaign_id = request.args.get('campaign')
    # Validate input
    if not campaign_id:
        return make_response(jsonify({'error': gettext('Missing "campaign" parameter')}), 400)
    try:
        campaign_id_int = int(campaign_id)
    except (TypeError, ValueError):
        return make_response(jsonify({'error': gettext('Invalid "campaign" parameter')}), 400)

    # Validate page/per_page ranges
    if page is not None and page <= 0:
        return make_response(jsonify({'error': gettext('Invalid "page" parameter')}), 400)
    if per_page is not None and per_page <= 0:
        return make_response(jsonify({'error': gettext('Invalid "per_page" parameter')}), 400)

    # Ensure campaign exists
    campaign = Campaign.query.get(campaign_id_int)
    if not campaign:
        return make_response(jsonify({'error': gettext('Campaign with id %(id)s does not exist', id=campaign_id_int)}), 404)

    # We get the current user's username
    username = session.get('username', None)
    try:
        data_points = get_stats_data_points(campaign_id_int, username, page, per_page)
        return jsonify(data_points)
    except Exception:
        app.logger.exception('Unexpected error while loading graph stats for campaign %s', campaign_id_int)
        return make_response(jsonify({'error': gettext('An internal error occurred')}), 500)


@campaigns.route('/api/post-contribution', methods=['POST'])
def postContribution():
    contrib_options_list = []
    contrib_data_list = request.json
    username = session.get('username', None)
    edits_recorded = 0

    # The most recent rev_id will be stored in latest_base_rev_id
    # Default is 0 meaning there is none and the edit failed
    latest_base_rev_id = 0
    # We get the session and app credetials for edits on Commons

    campaign_id = contrib_data_list[0]['campaign_id']
    if not username:
        flash(gettext('You need to login to participate'), 'info')
        # User is not logged in so we set the next url to redirect them after login
        session['next_url'] = request.url
        return redirect(url_for('campaigns.contributeToCampaign', id=campaign_id))

    user = User.query.filter_by(username=username).first()
    contrib_list = []
    suggestion_list = []
    for data in contrib_data_list:
        valid_actions = [
            "wbsetclaim",
            "wbremoveclaims",
            "wbsetlabel"
        ]
        if data["api_options"]["action"] not in valid_actions:
            abort(400)
        # Don't create a new contribution if it's an edit
        if data['edit_action'] != 'edit':
            contribution = Contribution(user=user,
                                        campaign_id=int(campaign_id),
                                        file=data['image'],
                                        edit_action=data['edit_action'],
                                        edit_type=data['edit_type'],
                                        country=data['country'],
                                        depict_item=data.get('depict_item'),
                                        depict_prominent=data.get('depict_prominent'),
                                        caption_language=data.get('caption_language'),
                                        caption_text=data.get('caption_text'),
                                        date=datetime.date(datetime.utcnow()))
            contrib_list.append(contribution)

        # Also create a new suggestion if depict item was suggested
        suggestion_keys = ['google_vision', 'metadata_to_concept']
        if any(key in data for key in suggestion_keys):
            suggestion = Suggestion(campaign_id=campaign_id,
                                    file_name=data['image'],
                                    depict_item=data['depict_item'],
                                    google_vision=data.get('google_vision'),
                                    google_vision_confidence=data.get('google_vision_confidence'),
                                    metadata_to_concept=data.get('metadata_to_concept'),
                                    metadata_to_concept_confidence=data.get('metadata_to_concept_confidence'),
                                    update_status=1,
                                    user_id=user.id)
            suggestion_list.append(suggestion)

    # We write the api_options for the contributions into a list
    for contrib_data in contrib_data_list:
        contrib_options_list.append(contrib_data['api_options'])

    for i in range(len(contrib_options_list)):
        # We make an api call with the current contribution data and get baserevid
        if "ISA_DEV" in app.config and app.config["ISA_DEV"]:
            # Just pretend that everything went fine without touching
            # commons.
            lastrevid = 1
            return make_response(str(lastrevid), 200)

        csrf_token, api_auth_token = generate_csrf_token(
            app.config['CONSUMER_KEY'], app.config['CONSUMER_SECRET'],
            session.get('access_token')['key'],
            session.get('access_token')['secret']
        )

        # The initial claim is not found in second requests
        if 'initial_claim' not in contrib_data_list[i].keys():
            contrib_data_list[i]['initial_claim'] = session.get('initial_claim')
        lastrevid = make_edit_api_call(csrf_token,
                                       api_auth_token,
                                       contrib_data_list[i])
        if lastrevid is not None:
            edits_recorded += 1
            # We check if the previous edit was successfull
            # We then add the contribution to the db session
            if len(contrib_list) > 0:
                db.session.add(contrib_list[i])

            # Check that there are still elements in the list in order to pop
            if len(contrib_options_list) > 1:
                # We take out the first element of the data list
                contrib_options_list.pop(0)

                # We assign the baserevid of the next data list of api_options
                # If there is a next element in the data list
                next_api_options = contrib_options_list[0]
                next_api_options['baserevid'] = lastrevid
        else:
            return make_response("Failure", 400)
        # We store the latest revision id to be sent to client
        latest_base_rev_id = lastrevid

    #  Before we commit changes we add the suggestions:
    for suggestion in suggestion_list:
        db.session.add(suggestion)

    # We attempt to save the changes to db if we have contributions
    if len(contrib_list) > 0:
        if commit_changes_to_db():
            return (str(latest_base_rev_id))
    # edit was made but not recorded in db
    if edits_recorded > 0:
        return (str(latest_base_rev_id))

    return make_response("Failure", 400)


@campaigns.route('/api/search-depicts/<int:id>')
def searchDepicts(id):
    # Ensure campaign exists
    campaign = Campaign.query.get(id)
    if not campaign:
        return make_response(jsonify({'error': gettext('Campaign with id %(id)s does not exist', id=id)}), 404)

    search_term = request.args.get('q')
    username = session.get('username', None)
    user = User.query.filter_by(username=username).first()
    if user and user.depicts_language:
        user_lang = user.depicts_language
    else:
        user_lang = session.get('lang', 'en')

    # Basic validation for search parameter
    if search_term is not None and not isinstance(search_term, str):
        return make_response(jsonify({'error': gettext('Invalid search parameter')}), 400)
    if search_term and len(search_term) > 200:
        return make_response(jsonify({'error': gettext('Search term too long')}), 400)

    headers = {'User-Agent': 'ISA/1.0 (contact: https://www.mediawiki.org/wiki/User:IsaBot)'}

    # If no search term provided, return top depicts for campaign
    if search_term is None or search_term == '':
        top_depicts = (Contribution.query
                       .with_entities(Contribution.depict_item)
                       .filter_by(campaign_id=id, edit_type="depicts", edit_action="add")
                       .group_by(Contribution.depict_item)
                       .order_by(func.count(Contribution.depict_item).desc())
                       .limit(5)
                       .all())

        if not top_depicts:
            return jsonify({"results": None})

        query_titles = '|'.join(depict for depict, in top_depicts if depict)
        if not query_titles:
            return jsonify({"results": None})

        try:
            resp = requests.get(
                url=app.config['WIKIDATA_SEARCH_API_URL'],
                params={
                    'action': 'wbgetentities',
                    'format': 'json',
                    'props': 'labels|descriptions',
                    'ids': query_titles,
                    'languages': user_lang,
                    'languagefallback': '',
                    'origin': '*'
                },
                headers=headers,
                timeout=8
            )
            resp.raise_for_status()
            depict_details = resp.json()
        except requests.RequestException:
            app.logger.exception('Wikidata API request failed for campaign %s', id)
            return make_response(jsonify({'error': gettext('Failed to contact Wikidata API')}), 502)
        except ValueError:
            app.logger.exception('Invalid JSON from Wikidata API for campaign %s', id)
            return make_response(jsonify({'error': gettext('Invalid response from Wikidata API')}), 502)

        top_depicts_return = []
        entities = depict_details.get('entities', {}) if isinstance(depict_details, dict) else {}
        for item, item_data in entities.items():
            if not isinstance(item_data, dict):
                continue
            text = item
            description = ''
            labels = item_data.get('labels', {})
            descriptions = item_data.get('descriptions', {})
            if user_lang in labels:
                text = labels[user_lang].get('value', text)
            if user_lang in descriptions:
                description = descriptions[user_lang].get('value', '')
            top_depicts_return.append({'id': item, 'text': text, 'description': description})

        if not top_depicts_return:
            top_depicts_return = None
        return jsonify({"results": top_depicts_return})

    # Otherwise perform a search on Wikidata
    try:
        resp = requests.get(
            url=app.config['WIKIDATA_SEARCH_API_URL'],
            params={
                'search': search_term,
                'action': 'wbsearchentities',
                'language': user_lang,
                'format': 'json',
                'uselang': user_lang,
                'origin': '*'
            },
            headers=headers,
            timeout=8
        )
        resp.raise_for_status()
        search_result = resp.json()
    except requests.RequestException:
        app.logger.exception('Wikidata search API request failed for campaign %s', id)
        return make_response(jsonify({'error': gettext('Failed to contact Wikidata API')}), 502)
    except ValueError:
        app.logger.exception('Invalid JSON from Wikidata search API for campaign %s', id)
        return make_response(jsonify({'error': gettext('Invalid response from Wikidata API')}), 502)

    search_return = []
    results_list = search_result.get('search') if isinstance(search_result, dict) else None
    if not results_list:
        return jsonify({"results": None})

    for search_result_item in results_list:
        if not isinstance(search_result_item, dict):
            continue
        search_return.append({
            'id': search_result_item.get('title'),
            'text': search_result_item.get('label'),
            'description': search_result_item.get('description', '')
        })

    if not search_return:
        search_return = None
    return jsonify({"results": search_return})


@campaigns.route('/campaigns/<int:id>/download_csv')
def downloadAllCampaignStats(id):

    campaign = Campaign.query.get(id)
    stats_file_directory = os.getcwd() + '/campaign_stats_files/' + str(campaign.id)

    # We create the all_stats download file
    # The field in the stats file will be as thus
    all_stats_fields = ['username', 'file', 'edit_type', 'edit_action', 'country', 'depict_item',
                        'depict_prominent', 'caption_text', 'caption_language', 'date']
    campaign_all_stats_data = get_all_camapaign_stats_data(id)
    stats_csv_file = create_campaign_all_stats_csv(stats_file_directory,
                                                   convert_latin_to_english(campaign.campaign_name),
                                                   all_stats_fields, campaign_all_stats_data)
    if stats_csv_file:
        return send_file(stats_file_directory + '/' + stats_csv_file, as_attachment=True)
    else:
        flash('Download may be unavailable now', 'info')


@campaigns.route('/campaigns/<int:campaign_id>/images', defaults={'country_name': None})
@campaigns.route('/campaigns/<int:campaign_id>/images/<string:country_name>')
def get_images(campaign_id, country_name):
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)

    # Start a query on the Image table directly
    query = Image.query.filter(Image.campaign_id == campaign_id)

    if country_name:
        country = Country.query.filter_by(name=country_name).first()
        if not country:
            return jsonify([])
        query = query.filter(Image.country_id == country.id)

    total_count = query.count()
    
    paginated_results = query.order_by(Image.page_id).offset((page - 1) * per_page).limit(per_page).all()
    
    # Extract the IDs
    paginated_images = [img.page_id for img in paginated_results]

    return jsonify({
        "images": paginated_images,
        "has_more": ((page - 1) * per_page + len(paginated_images)) < total_count
    })


@campaigns.route('/api/reject-suggestion', methods=['POST'])
def save_reject_statements():
    username = session.get('username')
    if not username:
        abort(401)
    # Require JSON body
    if not request.is_json:
        return make_response(jsonify({'error': gettext('Invalid or missing JSON body')}), 400)

    rejection_data = request.get_json()

    # Expected keys must be present
    expected_keys = {
        'file',
        'depict_item',
        'campaign_id',
        'google_vision',
        'google_vision_confidence',
        'metadata_to_concept',
        'metadata_to_concept_confidence'
    }

    if not expected_keys.issubset(set(rejection_data.keys())):
        return make_response(jsonify({'error': gettext('Missing required fields')}), 400)

    # Validate campaign_id and existence
    try:
        campaign_id = int(rejection_data['campaign_id'])
    except (TypeError, ValueError):
        return make_response(jsonify({'error': gettext('Invalid campaign id')}), 400)

    campaign = Campaign.query.get(campaign_id)
    if not campaign:
        return make_response(jsonify({'error': gettext('Campaign with id %(id)s does not exist', id=campaign_id)}), 404)

    # Basic validation for file and depict_item
    if not isinstance(rejection_data.get('file'), str) or not rejection_data.get('file'):
        return make_response(jsonify({'error': gettext('Invalid file')}), 400)
    if not isinstance(rejection_data.get('depict_item'), str) or not rejection_data.get('depict_item'):
        return make_response(jsonify({'error': gettext('Invalid depict_item')}), 400)

    # Validate confidence values (allow numeric strings too)
    def _validate_conf(val):
        if val is None or val == '':
            return True
        try:
            f = float(val)
            return 0.0 <= f <= 1.0
        except (TypeError, ValueError):
            return False

    if not _validate_conf(rejection_data.get('google_vision_confidence')):
        return make_response(jsonify({'error': gettext('Invalid google_vision_confidence')}), 400)
    if not _validate_conf(rejection_data.get('metadata_to_concept_confidence')):
        return make_response(jsonify({'error': gettext('Invalid metadata_to_concept_confidence')}), 400)

    # Find previous rejected suggestions for this file/depict combination
    file_rejected_suggestions = (Suggestion.query
                                 .filter_by(depict_item=rejection_data['depict_item'],
                                            file_name=rejection_data['file'], update_status=0)
                                 .all())

    user = User.query.filter_by(username=username).first()
    rejected_suggestion = Suggestion(campaign_id=campaign_id,
                                     file_name=rejection_data['file'],
                                     depict_item=rejection_data['depict_item'],
                                     google_vision=rejection_data.get('google_vision'),
                                     google_vision_confidence=rejection_data.get('google_vision_confidence'),
                                     metadata_to_concept=rejection_data.get('metadata_to_concept'),
                                     metadata_to_concept_confidence=rejection_data.get('metadata_to_concept_confidence'),
                                     user_id=user.id)

    if len(file_rejected_suggestions) > 1:
        rejected_suggestion.google_vision_submitted = rejection_data.get('google_vision')
        rejected_suggestion.metadata_to_concept_submitted = rejection_data.get('metadata_to_concept')

    db.session.add(rejected_suggestion)

    if not commit_changes_to_db():
        return make_response(jsonify({'error': gettext('Database commit failed')}), 400)
    return make_response(jsonify({'status': 'success'}), 200)


@campaigns.route('/api/get-rejected-statements', methods=['GET'])
def getRejectedStatements():
    username = session.get('username', None)
    if not username:
        abort(401)
    # Validate file parameter
    file_name = request.args.get('file')
    if not file_name:
        return make_response(jsonify({'error': gettext('Missing "file" parameter')}), 400)

    # Ensure user exists
    user = User.query.filter_by(username=username).first()
    if not user:
        return make_response(jsonify({'error': gettext('User not found')}), 404)

    # Query rejected suggestions for this user and file
    reject_suggestions = (Suggestion.query
                          .filter_by(user_id=user.id, file_name=file_name, update_status=0)
                          .all())

    if not reject_suggestions:
        return make_response(jsonify({'error': gettext('No rejected suggestions found')}), 404)

    return jsonify([data.depict_item for data in reject_suggestions])
