import unittest
from unittest.mock import patch

from creator_compass.data import DATASET_ID, load_development_subset
from creator_compass.topics import selected_topics, suggest_topics


class FakeStream:
    def take(self, limit):
        return iter([{'video_id': 'test-only-id', 'title': 'Test fixture'}][:limit])


class CoreTests(unittest.TestCase):
    @patch('creator_compass.data.load_dataset')
    def test_bounded_loader_and_observed_fields(self, load):
        load.return_value = {'actual_split': FakeStream()}
        sample = load_development_subset(limit=1)
        load.assert_called_once_with(DATASET_ID, 'videos', streaming=True)
        self.assertEqual(sample.split, 'actual_split')
        self.assertEqual(len(sample.records), 1)
        self.assertEqual(sample.fields['video title'], ['title'])
        self.assertEqual(sample.fields['comment text'], [])

    @patch('creator_compass.data.load_dataset')
    def test_errors_are_not_replaced_with_fake_records(self, load):
        load.side_effect = ConnectionError('blocked')
        with self.assertRaises(ConnectionError):
            load_development_subset()

    def test_invalid_size_rejected(self):
        for size in (0, 201):
            with self.assertRaises(ValueError):
                load_development_subset(size)

    @patch('creator_compass.data.load_dataset')
    def test_unknown_split_rejected(self, load):
        load.return_value = {'actual_split': FakeStream()}
        with self.assertRaises(ValueError):
            load_development_subset(split='train')

    def test_only_chosen_topics_continue(self):
        result = selected_topics([
            {'Select': False, 'Topic': 'Not selected'},
            {'Select': True, 'Topic': ' Edited topic '},
            {'Select': True, 'Topic': ' '},
        ], 'New topic\nedited TOPIC\n')
        self.assertEqual(result, ['Edited topic', 'New topic'])

    def test_suggestions_come_from_profile(self):
        topics = suggest_topics({'interests': 'Gardening', 'skills': 'Teaching', 'styles': ['Tutorials']})
        self.assertTrue(any('Gardening' in item['topic'] for item in topics))
        self.assertEqual(suggest_topics({}), [])


if __name__ == '__main__':
    unittest.main()
