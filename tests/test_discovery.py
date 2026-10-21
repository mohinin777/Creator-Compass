import unittest
from unittest.mock import patch

from creator_compass.data import load_video_catalog
from creator_compass.discovery import search_videos, group_creators, video_url


class DiscoveryTests(unittest.TestCase):
    def test_ranking_and_explanations_exclude_unrelated_titles(self):
        records = [
            {'video_id': 'aaaaaaaaaaa', 'title': 'Python gardening', 'channel_handle': '@one'},
            {'video_id': 'bbbbbbbbbbb', 'title': 'Python basics', 'channel_handle': '@one'},
            {'video_id': 'ccccccccccc', 'title': 'Cooking rice', 'channel_handle': '@two'},
            {'video_id': 'aaaaaaaaaaa', 'title': 'Python gardening', 'channel_handle': '@one'},
        ]
        matches = search_videos(records, 'Python gardening: a beginner’s guide')
        self.assertEqual(len(matches), 2)
        self.assertEqual(matches[0]['record']['video_id'], 'aaaaaaaaaaa')
        self.assertEqual(matches[0]['relevance'], 1.0)
        self.assertEqual(matches[0]['matched_terms'], ['gardening', 'python'])
        self.assertLess(matches[1]['relevance'], 1.0)
        self.assertEqual(group_creators(matches)[0]['matched_videos'], 2)

    def test_missing_fields_and_no_match_do_not_create_evidence(self):
        records = [{'title': None}, {'title': 'Python basics', 'author_hash': 'comment-author'}]
        matches = search_videos(records, 'Python')
        self.assertEqual(len(matches), 1)
        self.assertIsNone(matches[0]['source_url'])
        self.assertEqual(group_creators(matches), [])
        self.assertEqual(search_videos(records, 'unrelated'), [])
        self.assertEqual(search_videos(records, 'a beginner guide'), [])
        self.assertIsNone(video_url('invalid/id'))

    @patch('creator_compass.data.load_dataset')
    def test_catalog_truncation_and_exhaustion(self, load):
        class Stream:
            def take(self, count):
                return iter([{'video_id': str(i)} for i in range(3)][:count])
        load.return_value = {'observed_split': Stream()}
        limited = load_video_catalog(max_records=2)
        self.assertFalse(limited.complete)
        self.assertEqual(len(limited.records), 2)
        full = load_video_catalog(max_records=3)
        self.assertTrue(full.complete)
        self.assertEqual(full.split, 'observed_split')
