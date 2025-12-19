#!/usr/bin/env python3

# Author: Eugene Egbe
# Unit tests for the routes in the isa tool

from datetime import datetime
import json
import os
import sys
import unittest
from unittest import mock

from flask import session

# Ensure the project root (containing the "isa" package) is on sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from isa import app, db
from isa.models import Campaign, User, Contribution, Suggestion


class TestCampaignRoutes(unittest.TestCase):
    test_campaign_id = 0

    # executed prior to each test
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['DEBUG'] = False
        app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_TEST_DATABASE_URI']
        # Avoid external API calls for contributions
        app.config['ISA_DEV'] = True
        # Provide a dummy Wikidata API URL
        app.config.setdefault('WIKIDATA_SEARCH_API_URL', 'https://example.test/wikidata')

        self.app = app.test_client()
        db.create_all()

        # Minimal manager user to satisfy Campaign FK
        manager = User(username='TestUsername', caption_languages='en', depicts_language='en')
        db.session.add(manager)
        db.session.commit()

        test_campaign = Campaign(
            campaign_name='Test Campaign',
            categories='[{"name":"Test images","depth":"0"}]',
            campaign_images=100,
            start_date=datetime.strptime('2020-02-01', '%Y-%m-%d'),
            campaign_manager='TestUsername',
            manager_id=manager.id,
            end_date=None,
            status=False,
            short_description='Test campaign for unit test purposes',
            long_description='',
            creation_date=datetime.now().date(),
            depicts_metadata=1,
            campaign_image='',
            captions_metadata=0,
            campaign_type=0)
        db.session.add(test_campaign)
        db.session.commit()
        self.test_campaign_id = test_campaign.id

    # executed after each test
    def tearDown(self):
        db.session.close()
        db.drop_all()

    # helpers #

    def _login(self, username='TestUser'):
        """Helper to simulate a logged-in session user."""
        user = User.query.filter_by(username=username).first()
        if not user:
            user = User(username=username, caption_languages='en', depicts_language='en')
            db.session.add(user)
            db.session.commit()
        with self.app.session_transaction() as sess:
            sess['username'] = username
            sess['lang'] = 'en'
        return user

    # tests #

    def test_get_campaigns_route(self):
        response = self.app.get('/campaigns', follow_redirects=True)
        self.assertEqual(response.status_code, 200)

    def test_get_campaigns_paginated_basic(self):
        response = self.app.get('/api/campaigns?draw=1&start=0&length=10', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.data.decode('utf-8'))
        self.assertIn('recordsTotal', payload)
        self.assertIn('recordsFiltered', payload)
        self.assertIn('data', payload)
        self.assertEqual(len(payload['data']), 1)
        # Campaign name should be rendered into the HTML snippet
        self.assertIn('Test Campaign', str(payload['data'][0]['campaign_html']))
        # Active/ongoing campaigns should have status_flag 1
        self.assertEqual(payload['data'][0]['status_flag'], 1)

    def test_get_campaigns_paginated_page_per_page(self):
        # Use page/per_page instead of start/length
        response = self.app.get('/api/campaigns?page=1&per_page=1')
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.data.decode('utf-8'))
        self.assertEqual(payload['page'], 1)
        self.assertEqual(payload['per_page'], 1)
        self.assertFalse(payload['has_more'])

    def test_get_campaigns_paginated_search_filter(self):
        # Search by campaign name
        response = self.app.get('/api/campaigns?search_value=Test')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload['recordsFiltered'], 1)

        # Search for something that does not exist
        response = self.app.get('/api/campaigns?search_value=NoSuchCampaign')
        payload = response.get_json()
        self.assertEqual(payload['recordsFiltered'], 0)
        self.assertEqual(len(payload['data']), 0)

    def test_get_campaign_by_id_success(self):
        # Also exercise table stats / CSV path by stubbing get_table_stats
        with mock.patch('isa.campaigns.routes.get_table_stats') as mocked_get_stats:
            mocked_get_stats.return_value = {
                'all_campaign_country_statistics_data': [],
                'all_contributors_data': [],
                'campaign_editors': 0,
                'current_user_rank': None,
                'page_info': {}
            }
            response = self.app.get(f'/campaigns/{self.test_campaign_id}', follow_redirects=True)
            self.assertEqual(response.status_code, 200)

    def test_get_campaign_by_id_not_found(self):
        response = self.app.get('/campaigns/9999', follow_redirects=True)
        # Should redirect back to /campaigns
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'/campaigns', response.data)

    def test_get_campaign_table_data_success(self):
        with mock.patch('isa.campaigns.routes.get_table_stats') as mocked_get_stats:
            mocked_get_stats.return_value = {'page_info': {}, 'rows': []}
            response = self.app.get(f'/campaigns/{self.test_campaign_id}/table?page=1&per_page=10')
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertIn('page_info', payload)

    def test_get_campaign_table_data_invalid_page(self):
        response = self.app.get(f'/campaigns/{self.test_campaign_id}/table?page=abc')
        self.assertEqual(response.status_code, 400)

    def test_get_campaign_table_data_missing_campaign(self):
        response = self.app.get('/campaigns/9999/table')
        self.assertEqual(response.status_code, 404)

    def test_get_campaign_stats_by_id_success(self):
        # No contributions yet, but route should still render
        response = self.app.get(f'/campaigns/{self.test_campaign_id}/stats')
        self.assertEqual(response.status_code, 200)

    def test_get_campaign_stats_by_date_invalid_campaign(self):
        response = self.app.get('/api/campaigns/9999/stats_by_date')
        self.assertEqual(response.status_code, 404)

    def test_get_campaign_stats_by_date_invalid_date_format(self):
        response = self.app.get(f'/api/campaigns/{self.test_campaign_id}/stats_by_date?start_date=2020-13-01')
        self.assertEqual(response.status_code, 400)

    def test_get_campaign_stats_by_date_invalid_range(self):
        response = self.app.get(
            f'/api/campaigns/{self.test_campaign_id}/stats_by_date?start_date=2020-02-02&end_date=2020-02-01'
        )
        self.assertEqual(response.status_code, 400)

    def test_get_campaign_stats_by_date_success_empty(self):
        response = self.app.get(f'/api/campaigns/{self.test_campaign_id}/stats_by_date')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn('total_contributions', payload)
        self.assertEqual(payload['total_contributions'], 0)

    def test_get_campaign_categories_happy_path(self):
        response = self.app.get(f'/api/get-campaign-categories?campaign={self.test_campaign_id}')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        # New route returns a dict with 'categories'
        self.assertIn('categories', payload)

    def test_get_campaign_categories_missing_param(self):
        response = self.app.get('/api/get-campaign-categories')
        self.assertEqual(response.status_code, 400)

    def test_get_campaign_categories_unknown_campaign(self):
        response = self.app.get('/api/get-campaign-categories?campaign=9999')
        self.assertEqual(response.status_code, 404)

    def test_get_campaign_graph_stats_data_happy_path(self):
        with mock.patch('isa.campaigns.routes.get_stats_data_points') as mocked_points:
            mocked_points.return_value = {'points': []}
            response = self.app.get(f'/api/get-campaign-graph-stats-data?campaign={self.test_campaign_id}')
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertIn('points', payload)

    def test_get_campaign_graph_stats_data_missing_campaign_param(self):
        response = self.app.get('/api/get-campaign-graph-stats-data')
        self.assertEqual(response.status_code, 400)

    def test_get_campaign_graph_stats_data_invalid_campaign_param(self):
        response = self.app.get('/api/get-campaign-graph-stats-data?campaign=abc')
        self.assertEqual(response.status_code, 400)

    def test_get_campaign_graph_stats_data_unknown_campaign(self):
        response = self.app.get('/api/get-campaign-graph-stats-data?campaign=9999')
        self.assertEqual(response.status_code, 404)

    def test_search_depicts_missing_campaign(self):
        response = self.app.get('/api/search-depicts/9999')
        self.assertEqual(response.status_code, 404)

    def test_search_depicts_no_term_and_no_top_depicts(self):
        # No contributions inserted for this campaign, should return results: None
        response = self.app.get(f'/api/search-depicts/{self.test_campaign_id}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {'results': None})

    @mock.patch('isa.campaigns.routes.requests.get')
    def test_search_depicts_with_term_success(self, mocked_get):
        # Simulate a Wikidata search result
        mocked_response = mock.Mock()
        mocked_response.raise_for_status.return_value = None
        mocked_response.json.return_value = {
            'search': [{
                'title': 'Q4115189',
                'label': 'Wikidata Sandbox',
                'description': 'Test item'
            }]
        }
        mocked_get.return_value = mocked_response

        response = self.app.get(f'/api/search-depicts/{self.test_campaign_id}?q=Wikidata%20Sandbox')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIsInstance(payload['results'], list)
        self.assertEqual(payload['results'][0]['id'], 'Q4115189')

    def test_post_contribution_requires_login(self):
        payload = [{
            'campaign_id': self.test_campaign_id,
            'image': 'File:Test.jpg',
            'edit_action': 'add',
            'edit_type': 'depicts',
            'country': 'Testland',
            'api_options': {'action': 'wbsetclaim'}
        }]
        response = self.app.post('/api/post-contribution', json=payload, follow_redirects=False)
        # Should redirect to participate page when not logged in
        self.assertEqual(response.status_code, 302)

    def test_post_contribution_invalid_action(self):
        self._login()
        payload = [{
            'campaign_id': self.test_campaign_id,
            'image': 'File:Test.jpg',
            'edit_action': 'add',
            'edit_type': 'depicts',
            'country': 'Testland',
            'api_options': {'action': 'invalid'}
        }]
        response = self.app.post('/api/post-contribution', json=payload)
        self.assertEqual(response.status_code, 400)

    def test_post_contribution_success_records_contribution(self):
        user = self._login()
        # Ensure required tokens/config for the real code path
        with self.app.session_transaction() as sess:
            sess['access_token'] = {'key': 'test', 'secret': 'test'}

        original_isa_dev = app.config.get('ISA_DEV', False)
        app.config['ISA_DEV'] = False
        app.config['CONSUMER_KEY'] = 'dummy'
        app.config['CONSUMER_SECRET'] = 'dummy'

        payload = [{
            'campaign_id': self.test_campaign_id,
            'image': 'File:Test.jpg',
            'edit_action': 'add',
            'edit_type': 'depicts',
            'country': 'Testland',
            'api_options': {'action': 'wbsetclaim'}
        }]

        with mock.patch('isa.campaigns.routes.generate_csrf_token') as mocked_csrf, \
                mock.patch('isa.campaigns.routes.make_edit_api_call') as mocked_edit:
            mocked_csrf.return_value = ('token', 'auth')
            mocked_edit.return_value = 123
            response = self.app.post('/api/post-contribution', json=payload)

        # restore original flag
        app.config['ISA_DEV'] = original_isa_dev

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.decode('utf-8'), '123')
        contrib = Contribution.query.filter_by(user_id=user.id).first()
        self.assertIsNotNone(contrib)

    def test_save_reject_suggestion_requires_login(self):
        response = self.app.post('/api/reject-suggestion', json={})
        self.assertEqual(response.status_code, 401)

    def test_save_reject_suggestion_missing_fields(self):
        self._login()
        response = self.app.post('/api/reject-suggestion', json={})
        self.assertEqual(response.status_code, 400)

    def test_save_reject_suggestion_invalid_campaign(self):
        self._login()
        payload = {
            'file': 'File:Test.jpg',
            'depict_item': 'Q1',
            'campaign_id': 'abc',
            'google_vision': 0,
            'google_vision_confidence': 0.5,
            'metadata_to_concept': 0,
            'metadata_to_concept_confidence': 0.5,
        }
        response = self.app.post('/api/reject-suggestion', json=payload)
        self.assertEqual(response.status_code, 400)

    def test_save_reject_suggestion_happy_path(self):
        user = self._login()
        payload = {
            'file': 'File:Test.jpg',
            'depict_item': 'Q1',
            'campaign_id': str(self.test_campaign_id),
            'google_vision': 0,
            'google_vision_confidence': 0.5,
            'metadata_to_concept': 0,
            'metadata_to_concept_confidence': 0.5,
        }
        response = self.app.post('/api/reject-suggestion', json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['status'], 'success')
        suggestion = Suggestion.query.filter_by(user_id=user.id).first()
        self.assertIsNotNone(suggestion)

    def test_get_rejected_statements_requires_login(self):
        response = self.app.get('/api/get-rejected-statements?file=File:Test.jpg')
        self.assertEqual(response.status_code, 401)

    def test_get_rejected_statements_missing_file(self):
        self._login()
        response = self.app.get('/api/get-rejected-statements')
        self.assertEqual(response.status_code, 400)

    def test_get_rejected_statements_not_found(self):
        self._login()
        response = self.app.get('/api/get-rejected-statements?file=File:Test.jpg')
        self.assertEqual(response.status_code, 404)

    def test_get_rejected_statements_happy_path(self):
        user = self._login()
        suggestion = Suggestion(
            campaign_id=self.test_campaign_id,
            file_name='File:Test.jpg',
            depict_item='Q1',
            user_id=user.id,
            update_status=0,
        )
        db.session.add(suggestion)
        db.session.commit()

        with self.app.session_transaction() as sess:
            sess['username'] = user.username

        response = self.app.get('/api/get-rejected-statements?file=File:Test.jpg')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload, ['Q1'])


if __name__ == '__main__':
    unittest.main()
