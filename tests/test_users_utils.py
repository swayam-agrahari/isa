import unittest
from types import SimpleNamespace
from unittest.mock import patch
import os
import sys

# Ensure project root is on sys.path when running this file directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from isa.users.utils import (
	check_user_existence,
	add_user_to_db,
	get_user_language_preferences,
	get_user_ranking,
	get_current_user_images_improved,
	get_all_users_contribution_data_per_campaign,
	build_user_pref_lang,
)


class TestUsersUtils(unittest.TestCase):
	"""Tests for isa.users.utils helpers."""

	def test_check_user_existence_user_found(self):
		with patch('isa.users.utils.User') as mock_user_cls:
			user_obj = SimpleNamespace(username='alice')
			mock_user_cls.query.filter_by.return_value.first.return_value = user_obj

			result = check_user_existence('alice')

			self.assertIs(result, user_obj)

	def test_check_user_existence_user_not_found(self):
		with patch('isa.users.utils.User') as mock_user_cls:
			mock_user_cls.query.filter_by.return_value.first.return_value = None

			result = check_user_existence('bob')

			self.assertIsNone(result)

	def test_add_user_to_db_creates_new_user(self):
		with patch('isa.users.utils.check_user_existence') as mock_check, \
			 patch('isa.users.utils.User') as mock_user_cls, \
			 patch('isa.users.utils.db') as mock_db, \
			 patch('isa.users.utils.commit_changes_to_db') as mock_commit:

			mock_check.return_value = None
			user_obj = SimpleNamespace(username='charlie')
			mock_user_cls.return_value = user_obj
			mock_commit.return_value = True

			result = add_user_to_db('charlie')

			self.assertEqual(result, 'charlie')
			mock_db.session.add.assert_called_once_with(user_obj)
			mock_commit.assert_called_once()

	def test_add_user_to_db_existing_user(self):
		with patch('isa.users.utils.check_user_existence') as mock_check, \
			 patch('isa.users.utils.User') as mock_user_cls:

			user_obj = SimpleNamespace(username='dana')
			mock_check.return_value = user_obj
			mock_user_cls.query.filter_by.return_value.first.return_value = user_obj

			result = add_user_to_db('dana')

			self.assertEqual(result, 'dana')

	def test_get_user_language_preferences_user_not_found_defaults(self):
		with patch('isa.users.utils.User') as mock_user_cls:
			mock_user_cls.query.filter_by.return_value.first.return_value = None

			result = get_user_language_preferences('eve')

			self.assertEqual(result, ['en', 'fr'])

	def test_get_user_language_preferences_with_languages(self):
		with patch('isa.users.utils.User') as mock_user_cls:
			user_obj = SimpleNamespace(caption_languages='en,fr,es,,None')
			mock_user_cls.query.filter_by.return_value.first.return_value = user_obj

			result = get_user_language_preferences('frank')

			self.assertEqual(result, ['en', 'fr', 'es'])

	def test_get_user_language_preferences_empty_pref_falls_back_to_default(self):
		with patch('isa.users.utils.User') as mock_user_cls:
			user_obj = SimpleNamespace(caption_languages='None,,')
			mock_user_cls.query.filter_by.return_value.first.return_value = user_obj

			result = get_user_language_preferences('grace')

			self.assertEqual(result, ['en', 'fr'])

	def test_get_user_ranking_found(self):
		all_data = [
			{'username': 'alice', 'images_improved': 5},
			{'username': 'bob', 'images_improved': 3},
			{'username': 'charlie', 'images_improved': 1},
		]

		rank = get_user_ranking(all_data, 'bob')

		self.assertEqual(rank, 2)

	def test_get_user_ranking_not_found_returns_zero(self):
		all_data = [
			{'username': 'alice', 'images_improved': 5},
		]

		rank = get_user_ranking(all_data, 'nobody')

		self.assertEqual(rank, 0)

	def test_get_current_user_images_improved_found(self):
		all_data = [
			{'username': 'alice', 'images_improved': 5},
			{'username': 'bob', 'images_improved': 7},
		]

		images = get_current_user_images_improved(all_data, 'bob')

		self.assertEqual(images, 7)

	def test_get_current_user_images_improved_not_found_returns_zero(self):
		all_data = [
			{'username': 'alice', 'images_improved': 5},
		]

		images = get_current_user_images_improved(all_data, 'carol')

		self.assertEqual(images, 0)

	def test_get_all_users_contribution_data_per_campaign_sorts_descending(self):
		users = [
			SimpleNamespace(username='alice'),
			SimpleNamespace(username='bob'),
		]

		with patch('isa.users.utils.get_user_contrbition_per_campaign') as mock_get_contrib:
			mock_get_contrib.side_effect = [
				{'username': 'alice', 'images_improved': 3},
				{'username': 'bob', 'images_improved': 10},
			]

			data = get_all_users_contribution_data_per_campaign(users, campaign_id=1)

			self.assertEqual(len(data), 2)
			self.assertEqual(data[0]['username'], 'bob')
			self.assertEqual(data[0]['images_improved'], 10)
			self.assertEqual(data[1]['username'], 'alice')
			self.assertEqual(data[1]['images_improved'], 3)

	def test_build_user_pref_lang(self):
		result = build_user_pref_lang('en', 'fr', 'es', 'de', 'it', 'pt')
		self.assertEqual(result, 'en,fr,es,de,it,pt')


if __name__ == '__main__':
	unittest.main()

