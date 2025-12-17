import os

from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify
from flask_login import current_user
from sqlalchemy import text,func, extract
from isa import  db
import statistics
# from isa import app, db, gettext

from isa import gettext
from isa.users.utils import add_user_to_db
from isa.models import Contribution 
import time

# Simple in-memory cache to avoid recomputing heavy stats when multiple
# endpoints are requested in parallel. TTL is short to keep data fresh.
_stats_cache = {
    'ts': 0,
    'data': None
}
_STATS_CACHE_TTL = 30  # seconds


def _compute_stats_cached():
    """Compute stats and cache result for a short TTL."""
    now = time.time()
    if _stats_cache['data'] and (now - _stats_cache['ts'] < _STATS_CACHE_TTL):
        return _stats_cache['data']

    # Build stats (extracted from previous implementation)
    try:
        min_max_years = db.session.query(
            func.min(extract('year', Contribution.date)),
            func.max(extract('year', Contribution.date))
        ).one()

        if not min_max_years[0]:
            # No contributions found — return a structured empty response so
            # frontend can display a friendly empty-state instead of empty charts.
            empty_stats = {
                "has_data": False,
                "growth_trends": {"years": [], "contributions": [], "contributors": []},
                "yoy_change": {"years": [], "contribution_change": [], "contributor_change": []},
                "distribution": {},
                "averages": {"years": [], "average": [], "median": []},
                "detailed_stats": {}
            }
            _stats_cache['data'] = empty_stats
            _stats_cache['ts'] = now
            return empty_stats

        start_year = int(min_max_years[0])
        end_year = int(min_max_years[1])
        all_years = list(range(start_year, end_year + 1))

        yearly_stats = {}

        for year in all_years:
            contributions_this_year = db.session.query(Contribution).filter(
                extract('year', Contribution.date) == year
            )
            total_contributions = contributions_this_year.count()

            if total_contributions == 0:
                yearly_stats[year] = {
                    "num_contributions": 0, "num_contributors": 0,
                    "max_contributions": 0, "min_contributions": 0,
                    "avg_contributions": 0, "median_contributions": 0,
                    "top_5_share": 0, "top_10_share": 0, "top_20_share": 0,
                }
                continue

            num_contributors = db.session.query(func.count(func.distinct(Contribution.user_id))).filter(
                extract('year', Contribution.date) == year
            ).scalar()

            contribs_per_user_query = db.session.query(
                func.count(Contribution.id).label('contrib_count')
            ).filter(
                extract('year', Contribution.date) == year
            ).group_by(
                Contribution.user_id
            ).subquery()

            contribs_per_user = [c.contrib_count for c in db.session.query(contribs_per_user_query).all()]
            contribs_per_user.sort(reverse=True)

            total_users = len(contribs_per_user)
            idx_5_percent = max(1, round(total_users * 0.05))
            idx_10_percent = max(1, round(total_users * 0.10))
            idx_20_percent = max(1, round(total_users * 0.20))

            contribs_top_5 = sum(contribs_per_user[:idx_5_percent])
            contribs_top_10 = sum(contribs_per_user[:idx_10_percent])
            contribs_top_20 = sum(contribs_per_user[:idx_20_percent])

            yearly_stats[year] = {
                "num_contributions": total_contributions,
                "num_contributors": num_contributors,
                "max_contributions": contribs_per_user[0] if contribs_per_user else 0,
                "min_contributions": contribs_per_user[-1] if contribs_per_user else 0,
                "avg_contributions": round(statistics.mean(contribs_per_user)) if contribs_per_user else 0,
                "median_contributions": round(statistics.median(contribs_per_user)) if contribs_per_user else 0,
                "top_5_share": round((contribs_top_5 / total_contributions) * 100) if total_contributions > 0 else 0,
                "top_10_share": round((contribs_top_10 / total_contributions) * 100) if total_contributions > 0 else 0,
                "top_20_share": round((contribs_top_20 / total_contributions) * 100) if total_contributions > 0 else 0,
            }

        growth_trends = {
            "years": [str(y) for y in all_years],
            "contributions": [yearly_stats.get(y, {}).get("num_contributions", 0) for y in all_years],
            "contributors": [yearly_stats.get(y, {}).get("num_contributors", 0) for y in all_years]
        }

        yoy_years = []
        yoy_contrib_change = []
        yoy_contributors_change = []
        for i, year in enumerate(all_years):
            if i == 0:
                continue
            prev_year_stats = yearly_stats.get(all_years[i - 1])
            current_year_stats = yearly_stats.get(year)

            prev_contribs = prev_year_stats.get("num_contributions")
            curr_contribs = current_year_stats.get("num_contributions")
            if prev_contribs and prev_contribs > 0:
                change = round(((curr_contribs - prev_contribs) / prev_contribs) * 100)
                yoy_contrib_change.append(change)
            else:
                yoy_contrib_change.append(0)

            prev_contributors = prev_year_stats.get("num_contributors")
            curr_contributors = current_year_stats.get("num_contributors")
            if prev_contributors and prev_contributors > 0:
                change = round(((curr_contributors - prev_contributors) / prev_contributors) * 100)
                yoy_contributors_change.append(change)
            else:
                yoy_contributors_change.append(0)

            yoy_years.append(str(year))

        distribution = {str(y): {"top_5_share": s.get('top_5_share'), "top_10_share": s.get('top_10_share'), "top_20_share": s.get('top_20_share')} for y, s in yearly_stats.items()}
        averages = {
            "years": [str(y) for y in all_years],
            "average": [yearly_stats.get(y, {}).get("avg_contributions", 0) for y in all_years],
            "median": [yearly_stats.get(y, {}).get("median_contributions", 0) for y in all_years]
        }

        final_response = {
            "growth_trends": growth_trends,
            "yoy_change": {
                "years": yoy_years,
                "contribution_change": yoy_contrib_change,
                "contributor_change": yoy_contributors_change
            },
            "distribution": distribution,
            "averages": averages,
            "detailed_stats": {str(y): s for y, s in yearly_stats.items()}
        }

        # Mark that we have data so frontend can distinguish empty responses.
        final_response["has_data"] = True

        _stats_cache['data'] = final_response
        _stats_cache['ts'] = now
        return final_response
    except Exception as e:
        print(f"Error building stats: {e}")
        return None

main = Blueprint('main', __name__)


@main.route('/')
def home():
    username = session.get('username', None)
    directory = os.getcwd() + '/campaign_stats_files/'
    session_language = session.get('lang', None)

    if not os.path.exists(directory):
        os.makedirs(directory)
    if not session_language:
        session_language = 'en'

    session['next_url'] = request.url
    return render_template('main/home.html',
                           title='Home',
                           session_language=session_language,
                           username=username,
                           current_user=current_user)


@main.route('/help')
def help():
    username = session.get('username', None)
    session_language = session.get('lang', None)
    username_for_current_user = add_user_to_db(username)
    session['next_url'] = request.url
    if not session_language:
        session_language = 'en'
    return render_template('main/help.html',
                           title='Help',
                           session_language=session_language,
                           username=username_for_current_user,
                           current_user=current_user)


@main.route('/set_language', methods=['GET', 'POST'])
def set_language():
    lang = request.args.get('language', 'en')
    session['lang'] = lang
    return redirect(session.get('next_url', url_for('main.home')))

@main.route('/api/stats')
def get_all_statistics():
    """
    This single endpoint computes all statistics needed for the dashboard.
    It returns a comprehensive JSON object containing data for all charts and the table.
    """
    try:
        stats = _compute_stats_cached()
        # Only treat None as an error. If stats is a valid empty-structure
        # (has_data=False) return it so frontend can show a friendly message.
        if stats is None:
            return jsonify({"error": "No contribution data found"}), 404
        return jsonify(stats)

    except Exception as e:
        print(f"Error in statistics API: {e}")
        return jsonify({"error": "An internal error occurred"}), 500


@main.route('/api/stats/growth_trends')
def stats_growth_trends():
    stats = _compute_stats_cached()
    if stats is None:
        return jsonify({"error": "No contribution data found"}), 404
    return jsonify(stats.get('growth_trends', {}))


@main.route('/api/stats/yoy_change')
def stats_yoy_change():
    stats = _compute_stats_cached()
    if stats is None:
        return jsonify({"error": "No contribution data found"}), 404
    return jsonify(stats.get('yoy_change', {}))


@main.route('/api/stats/distribution')
def stats_distribution():
    stats = _compute_stats_cached()
    if stats is None:
        return jsonify({"error": "No contribution data found"}), 404
    return jsonify(stats.get('distribution', {}))


@main.route('/api/stats/averages')
def stats_averages():
    stats = _compute_stats_cached()
    if stats is None:
        return jsonify({"error": "No contribution data found"}), 404
    return jsonify(stats.get('averages', {}))


@main.route('/api/stats/detailed')
def stats_detailed():
    stats = _compute_stats_cached()
    if stats is None:
        return jsonify({"error": "No contribution data found"}), 404
    return jsonify(stats.get('detailed_stats', {}))


@main.route('/statistics')
def show_statistics():
    username = session.get('username', None)
    session_language = session.get('lang', None)
    if not session_language:
        session_language = 'en'
    session['next_url'] = request.url
    return render_template('main/stats.html',
                           title='Statistics',
                           session_language=session_language,
                           username=username,
                           current_user=current_user)