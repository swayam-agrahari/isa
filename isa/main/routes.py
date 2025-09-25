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
        # --- 1. Determine the range of years with contributions ---
        min_max_years = db.session.query(
            func.min(extract('year', Contribution.date)),
            func.max(extract('year', Contribution.date))
        ).one()

        if not min_max_years[0]:
            return jsonify({"error": "No contribution data found"}), 404
        
        start_year = int(min_max_years[0])
        end_year = int(min_max_years[1])
        all_years = list(range(start_year, end_year + 1))

        # --- 2. Calculate stats for each year ---
        yearly_stats = {}

        for year in all_years:
            # Get all contributions for the current year
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

            # Calculate total unique contributors for the year
            num_contributors = db.session.query(func.count(func.distinct(Contribution.user_id))).filter(
                extract('year', Contribution.date) == year
            ).scalar()

            # Subquery to get contribution count per user for this year
            contribs_per_user_query = db.session.query(
                func.count(Contribution.id).label('contrib_count')
            ).filter(
                extract('year', Contribution.date) == year
            ).group_by(
                Contribution.user_id
            ).subquery()
            
            # Get a flat list of contribution counts: [120, 50, 5, ...]
            contribs_per_user = [c.contrib_count for c in db.session.query(contribs_per_user_query).all()]
            contribs_per_user.sort(reverse=True) # Sort descending for distribution calcs

            # --- Calculate distribution (top 5%, 10%, 20%) ---
            total_users = len(contribs_per_user)
            idx_5_percent = max(1, round(total_users * 0.05))
            idx_10_percent = max(1, round(total_users * 0.10))
            idx_20_percent = max(1, round(total_users * 0.20))

            contribs_top_5 = sum(contribs_per_user[:idx_5_percent])
            contribs_top_10 = sum(contribs_per_user[:idx_10_percent])
            contribs_top_20 = sum(contribs_per_user[:idx_20_percent])
            
            # --- Store all calculated stats for the year ---
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

        # --- 3. Format the data for the frontend components ---
        # Note: 'or [0]' is used as a fallback for empty data
        
        # Line Chart: Growth Trends
        growth_trends = {
            "years": [str(y) for y in all_years],
            "contributions": [yearly_stats.get(y, {}).get("num_contributions", 0) for y in all_years],
            "contributors": [yearly_stats.get(y, {}).get("num_contributors", 0) for y in all_years]
        }
        
        # Bar Chart: Year-over-Year Change
        yoy_years = []
        yoy_contrib_change = []
        yoy_contributors_change = []
        for i, year in enumerate(all_years):
            if i == 0: continue # Cannot calculate change for the first year
            prev_year_stats = yearly_stats.get(all_years[i-1])
            current_year_stats = yearly_stats.get(year)

            # Contribution % change
            prev_contribs = prev_year_stats.get("num_contributions")
            curr_contribs = current_year_stats.get("num_contributions")
            if prev_contribs and prev_contribs > 0:
                change = round(((curr_contribs - prev_contribs) / prev_contribs) * 100)
                yoy_contrib_change.append(change)
            else:
                yoy_contrib_change.append(0) # or None, depending on frontend preference

            # Contributor % change
            prev_contributors = prev_year_stats.get("num_contributors")
            curr_contributors = current_year_stats.get("num_contributors")
            if prev_contributors and prev_contributors > 0:
                change = round(((curr_contributors - prev_contributors) / prev_contributors) * 100)
                yoy_contributors_change.append(change)
            else:
                yoy_contributors_change.append(0)
            
            yoy_years.append(str(year))
            
        # Donut & Avg Charts
        distribution = {str(y): {"top_5_share": s.get('top_5_share'), "top_10_share": s.get('top_10_share'), "top_20_share": s.get('top_20_share')} for y, s in yearly_stats.items()}
        averages = {
            "years": [str(y) for y in all_years],
            "average": [yearly_stats.get(y, {}).get("avg_contributions", 0) for y in all_years],
            "median": [yearly_stats.get(y, {}).get("median_contributions", 0) for y in all_years]
        }

        # --- 4. Assemble the final response object ---
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
        
        return jsonify(final_response)

    except Exception as e:
        # Basic error handling
        print(f"Error in statistics API: {e}")
        return jsonify({"error": "An internal error occurred"}), 500


@main.route('/statistics')
def show_statistics():
    return render_template('main/stats.html')