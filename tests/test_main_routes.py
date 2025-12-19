#!/usr/bin/env python3

# Author: Eugene Egbe
# Unit tests for the routes in the isa tool

import json
import os
import sys
import unittest

# Ensure project root (containing the `isa` package) is on sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from isa import app, db
from isa.main.routes import _stats_cache
from isa.models import User, Campaign, Contribution


class TestMain(unittest.TestCase):
    
    # setup and teardown #

    # executed prior to each test
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['DEBUG'] = False
        # Use dedicated test database, not production DB
        app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_TEST_DATABASE_URI']
        self.app = app.test_client()
        db.create_all()

        # Reset in-memory stats cache before each test to avoid cross-test leakage
        _stats_cache['data'] = None
        _stats_cache['ts'] = 0

    # executed after each test
    def tearDown(self):
        db.session.remove()
        db.drop_all()
    
    # tests #

    def test_home_route(self):
        response = self.app.get('/', follow_redirects=True)
        self.assertEqual(response.status_code, 200)

    def test_help_route(self):
        response = self.app.get('/help', follow_redirects=True)
        self.assertEqual(response.status_code, 200)

    def test_statistics_page_route(self):
        response = self.app.get('/statistics', follow_redirects=True)
        self.assertEqual(response.status_code, 200)

    def test_stats_api_empty_database(self):
        response = self.app.get('/api/stats', follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        payload = json.loads(response.data.decode('utf-8'))
        self.assertIn('has_data', payload)
        self.assertFalse(payload['has_data'])
        self.assertIn('growth_trends', payload)
        self.assertIn('yoy_change', payload)
        self.assertIn('distribution', payload)
        self.assertIn('averages', payload)
        self.assertIn('detailed_stats', payload)

    def test_stats_api_sub_endpoints_empty_database(self):
        # Ensure base stats call initializes cache for empty DB
        self.app.get('/api/stats', follow_redirects=True)

        growth = json.loads(self.app.get('/api/stats/growth_trends', follow_redirects=True).data.decode('utf-8'))
        yoy = json.loads(self.app.get('/api/stats/yoy_change', follow_redirects=True).data.decode('utf-8'))
        distribution = json.loads(self.app.get('/api/stats/distribution', follow_redirects=True).data.decode('utf-8'))
        averages = json.loads(self.app.get('/api/stats/averages', follow_redirects=True).data.decode('utf-8'))
        detailed = json.loads(self.app.get('/api/stats/detailed', follow_redirects=True).data.decode('utf-8'))

        # Growth trends structure
        self.assertIn('years', growth)
        self.assertIn('contributions', growth)
        self.assertIn('contributors', growth)
        self.assertEqual(growth['years'], [])

        # YoY change structure
        self.assertIn('years', yoy)
        self.assertIn('contribution_change', yoy)
        self.assertIn('contributor_change', yoy)

        # Distribution and averages should be empty mappings/arrays
        self.assertIsInstance(distribution, dict)
        self.assertIn('years', averages)
        self.assertIn('average', averages)
        self.assertIn('median', averages)
        self.assertIsInstance(detailed, dict)

    def _create_sample_data(self):
        """Helper to insert minimal data for non-empty stats tests."""
        user = User(username='testuser', caption_languages='en', depicts_language='en')
        db.session.add(user)
        db.session.commit()

        campaign = Campaign(
            campaign_name='Test Campaign',
            categories='[]',
            manager_id=user.id,
            short_description='short',
            long_description='long',
            depicts_metadata=True,
            captions_metadata=True,
            campaign_type=False,
        )
        db.session.add(campaign)
        db.session.commit()

        # Two years of contributions to exercise YoY and growth logic
        db.session.add(Contribution(
            username='testuser',
            user_id=user.id,
            campaign_id=campaign.id,
            file='file1.jpg',
            edit_type='create',
            edit_action='add',
            country='XX',
            caption_language='en',
            caption_text='caption 1',
        ))
        db.session.add(Contribution(
            username='testuser',
            user_id=user.id,
            campaign_id=campaign.id,
            file='file2.jpg',
            edit_type='create',
            edit_action='add',
            country='XX',
            caption_language='en',
            caption_text='caption 2',
        ))
        db.session.commit()

    def test_stats_api_populated_database(self):
        self._create_sample_data()

        response = self.app.get('/api/stats', follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        payload = json.loads(response.data.decode('utf-8'))
        self.assertIn('has_data', payload)
        self.assertTrue(payload['has_data'])
        self.assertIn('growth_trends', payload)
        self.assertIn('yoy_change', payload)
        self.assertIn('distribution', payload)
        self.assertIn('averages', payload)
        self.assertIn('detailed_stats', payload)

        growth = payload['growth_trends']
        self.assertGreaterEqual(len(growth.get('years', [])), 1)

    def test_stats_api_sub_endpoints_populated_database(self):
        self._create_sample_data()

        growth = json.loads(self.app.get('/api/stats/growth_trends', follow_redirects=True).data.decode('utf-8'))
        yoy = json.loads(self.app.get('/api/stats/yoy_change', follow_redirects=True).data.decode('utf-8'))
        distribution = json.loads(self.app.get('/api/stats/distribution', follow_redirects=True).data.decode('utf-8'))
        averages = json.loads(self.app.get('/api/stats/averages', follow_redirects=True).data.decode('utf-8'))
        detailed = json.loads(self.app.get('/api/stats/detailed', follow_redirects=True).data.decode('utf-8'))

        self.assertIn('years', growth)
        self.assertIn('contributions', growth)
        self.assertIn('contributors', growth)
        self.assertGreaterEqual(len(growth['years']), 1)

        self.assertIn('years', yoy)
        self.assertIn('contribution_change', yoy)
        self.assertIn('contributor_change', yoy)

        self.assertIsInstance(distribution, dict)
        self.assertGreaterEqual(len(distribution.keys()), 1)

        self.assertIn('years', averages)
        self.assertIn('average', averages)
        self.assertIn('median', averages)

        self.assertIsInstance(detailed, dict)
        self.assertGreaterEqual(len(detailed.keys()), 1)


if __name__ == '__main__':
    unittest.main()
