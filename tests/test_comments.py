import json
import os
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from datetime import datetime, timezone

from creator_compass.comments import sample_records, load_comment_sample
from creator_compass.classification import classify_comments, validate_classifications, aggregate_categories, CATEGORIES

A, B = 'aaaaaaaaaaa', 'bbbbbbbbbbb'


def comment(identity, video=A, text='Please show a tutorial'):
    return {'comment_id': identity, 'video_id': video, 'text': text}


class CommentTests(unittest.TestCase):
    def test_bounded_sampling_filters_duplicates_and_reports_coverage(self):
        rows = [comment('c1'), comment('c1'), comment('bad', text=''),
                comment('other', 'ccccccccccc'), comment('c2'), comment('c3', B)]
        sample = sample_records(rows, [A, B], 2, 5, 'revision', 'split')
        self.assertEqual([r['comment_id'] for r in sample.records], ['c1', 'c2'])
        self.assertEqual(sample.scanned, 5)
        self.assertEqual(sample.stop_reason, 'scan limit reached')
        self.assertEqual(sample.coverage()[1]['sampled_comments'], 0)
        short = sample_records(rows, [A], 1, 10, 'revision', 'split')
        self.assertEqual(short.scanned, 1)
        self.assertEqual(short.stop_reason, 'all sample targets reached')
        empty = sample_records([], [A], 1, 10, 'revision', 'split')
        self.assertEqual(empty.stop_reason, 'split exhausted')
        self.assertEqual(empty.records, [])

    @patch('creator_compass.comments.load_dataset')
    @patch('creator_compass.comments.HfApi')
    def test_revision_keyed_cache_reuses_sample(self, api, load):
        api.return_value.dataset_info.return_value = SimpleNamespace(sha='revision1')
        load.return_value = {'train': [{**comment('c1'), 'published_at': datetime(2026, 1, 1, tzinfo=timezone.utc)}]}
        with tempfile.TemporaryDirectory() as directory:
            first = load_comment_sample([A], 1, 10, directory)
            second = load_comment_sample([A], 1, 10, directory)
            self.assertEqual(first, second)
            self.assertEqual(load.call_count, 1)
            api.return_value.dataset_info.return_value.sha = 'revision2'
            load_comment_sample([A], 1, 10, directory)
            self.assertEqual(load.call_count, 2)
        load.assert_called_with('brianhliou/youtube-comment-exposure', 'comments', revision='revision2', streaming=True)

    def test_validation_rejects_hallucinations_and_incomplete_results(self):
        originals = [comment('c1')]
        good = [{'comment_id': 'c1', 'category': CATEGORIES[0], 'quote': 'show a tutorial'}]
        self.assertEqual(validate_classifications(good, originals), good)
        for bad in [[], good * 2,
                    [{**good[0], 'comment_id': 'invented'}],
                    [{**good[0], 'category': 'Unreviewed'}],
                    [{**good[0], 'quote': 'not in source'}],
                    [{**good[0], 'quote': ''}]]:
            with self.assertRaises(ValueError):
                validate_classifications(bad, originals)

    def test_aggregation_counts_distinct_videos(self):
        comments = [comment('c1'), comment('c2'), comment('c3', B)]
        rows = [{'comment_id': r['comment_id'], 'category': CATEGORIES[0], 'quote': 'tutorial'} for r in comments]
        summary = aggregate_categories(comments, rows)[0]
        self.assertEqual(summary['comments'], 3)
        self.assertEqual(summary['distinct_videos'], 2)
        self.assertEqual(summary['evidence'][0]['video_id'], A)

    @patch.dict(os.environ, {'LLM_API_KEY2': 'test-only-key', 'LLM_MODEL': 'test-model', 'LLM_BASE_URL': 'https://api.openai.com/v1'})
    @patch('creator_compass.classification.urlopen')
    def test_llm_request_validates_output_without_live_calls(self, urlopen):
        response = {'choices': [{'message': {'content': json.dumps({'results': [
            {'comment_id': 'c1', 'category': CATEGORIES[0], 'quote': 'tutorial'}]})}}]}
        import io
        urlopen.return_value.__enter__.return_value = io.StringIO(json.dumps(response))
        rows = classify_comments([comment('c1')])
        self.assertEqual(rows[0]['quote'], 'tutorial')
        payload = json.loads(urlopen.call_args.args[0].data)
        self.assertEqual(payload['response_format']['type'], 'json_schema')
        self.assertEqual(payload['model'], 'test-model')

    @patch.dict(os.environ, {'LLM_API_KEY2': ''})
    def test_absent_key_does_not_claim_classification(self):
        with self.assertRaises(ValueError):
            classify_comments([comment('c1')])

    @patch.dict(os.environ, {'LLM_API_KEY2': 'test-only-key'})
    @patch('creator_compass.classification.urlopen')
    def test_provider_errors_do_not_expose_response_or_credentials(self, urlopen):
        urlopen.side_effect = RuntimeError('sensitive provider body test-only-key')
        with self.assertRaises(RuntimeError) as caught:
            classify_comments([comment('c1')])
        self.assertNotIn('test-only-key', str(caught.exception))
        self.assertNotIn('sensitive', str(caught.exception))
