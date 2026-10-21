import itertools
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from creator_compass.comments import load_comment_sample
from creator_compass.comment_index import build_index, index_path

A, B = 'aaaaaaaaaaa', 'bbbbbbbbbbb'


def row(identity, video):
    return {'comment_id': identity, 'video_id': video, 'text': 'Actual test fixture text'}


class IndexTests(unittest.TestCase):
    @patch('creator_compass.comments.HfApi')
    @patch('creator_compass.comments.load_dataset')
    def test_full_scan_finds_late_video_and_reuses_index_for_other_selections(self, load, api):
        api.return_value.dataset_info.return_value = SimpleNamespace(sha='commit1')
        # The first target is already satisfied at row 1, but indexing must not stop.
        records = itertools.chain([row('c1', A)], itertools.repeat(row('duplicate', A), 100000), [row('late', B)])
        load.return_value = {'train': records}
        with tempfile.TemporaryDirectory() as directory:
            first = load_comment_sample([A], per_video=1, cache_dir=directory)
            second = load_comment_sample([B], per_video=1, cache_dir=directory)
            self.assertEqual(first.scanned, 100002)
            self.assertEqual(first.stop_reason, 'full split indexed')
            self.assertIsNone(first.max_scan)
            self.assertEqual(second.records[0]['comment_id'], 'late')
            self.assertEqual(load.call_count, 1)
            api.return_value.dataset_info.return_value.sha = 'commit2'
            load.return_value = {'train': [row('new', B)]}
            revised = load_comment_sample([B], per_video=1, cache_dir=directory)
            self.assertEqual(revised.records[0]['comment_id'], 'new')
            self.assertEqual(load.call_count, 2)

    def test_failed_build_never_publishes_partial_index(self):
        def interrupted():
            yield row('first', A)
            raise ConnectionError('Interrupted stream')
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ConnectionError):
                build_index(interrupted(), directory, 'commit', 'train')
            self.assertFalse(index_path(directory, 'commit').exists())
            self.assertEqual(list(Path(directory).iterdir()), [])
