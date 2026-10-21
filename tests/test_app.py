from pathlib import Path
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from creator_compass.data import VideoCatalog
from creator_compass.comments import CommentSample
from creator_compass.classification import CATEGORIES

APP = str(Path(__file__).resolve().parents[1] / 'app.py')


class AppTests(unittest.TestCase):
    @patch.dict('os.environ', {'LLM_API_KEY2': ''})
    @patch('creator_compass.comment_ui.load_comment_sample')
    def test_comment_sampling_manual_review_and_stale_settings(self, load):
        identity = 'aaaaaaaaaaa'
        load.return_value = CommentSample('revision', 'train', [identity], 20, 100000,
            1, 'split exhausted', [{'video_id': identity, 'comment_id': 'c1', 'text': 'Great video'}])
        app = AppTest.from_file(APP)
        app.session_state['chosen_topics'] = ['Gardening']
        app.session_state['video_catalog'] = VideoCatalog('train', [
            {'video_id': identity, 'title': 'Gardening basics', 'channel_handle': '@fixture'}], True)
        app.run()
        next(x for x in app.button if x.label == 'Sample real comments').click().run()
        self.assertFalse(app.exception)
        self.assertTrue(next(x for x in app.button if x.label == 'Classify sampled comments with LLM').disabled)
        self.assertTrue(any('fewer comments' in x.value for x in app.warning))
        context = ('Gardening', (identity,), 20, 100000)
        key = 'review_' + str(hash((context, ('c1',), repr({}))))
        app.session_state[key] = {'edited_rows': {0: {'category': CATEGORIES[-1]}}, 'added_rows': [], 'deleted_rows': []}
        next(x for x in app.button if x.label == 'Save reviewed categories').click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any('Human reviewed' in x.value for x in app.caption))
        next(x for x in app.select_slider if x.label == 'Comments per video').set_value(30).run()
        self.assertFalse(app.exception)
        self.assertFalse(any('Human reviewed' in x.value for x in app.caption))

    @patch('creator_compass.data.load_video_catalog')
    def test_discovery_uses_only_confirmed_topics(self, load):
        load.return_value = VideoCatalog('train', [
            {'video_id': 'aaaaaaaaaaa', 'title': 'Gardening basics', 'channel_handle': '@fixture'},
            {'video_id': 'bbbbbbbbbbb', 'title': 'Cooking rice', 'channel_handle': '@other'},
        ], True)
        app = AppTest.from_file(APP).run()
        self.assertFalse(any(x.label == 'Load video catalog and discover creators' for x in app.button))
        app.text_area[0].set_value('Gardening, Cooking')
        app.button[0].click().run()
        next(x for x in app.text_area if x.label.startswith('Add your own')).set_value('Gardening')
        next(x for x in app.button if x.label == 'Confirm selected topics').click().run()
        next(x for x in app.button if x.label == 'Load video catalog and discover creators').click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any('1 matching videos' in x.value for x in app.markdown))
        frames = [str(x.value) for x in app.dataframe]
        self.assertTrue(any('Gardening basics' in frame for frame in frames))
        self.assertFalse(any('Cooking rice' in frame for frame in frames))

    def test_profile_topics_confirmation_and_profile_reset(self):
        app = AppTest.from_file(APP).run()
        self.assertFalse(app.exception)
        self.assertTrue(any('before analysis' in w.value for w in app.warning))
        app.text_area[0].set_value('Gardening, Cooking')
        app.text_area[1].set_value('Teaching')
        app.text_area[4].set_value('User-supplied resume reference')
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertIn('suggestions', app.session_state)
        self.assertFalse('chosen_topics' in app.session_state)
        # Custom additions are supported even without selecting a suggested row.
        next(x for x in app.text_area if x.label.startswith('Add your own')).set_value('Balcony gardening\nCooking on a budget')
        next(x for x in app.button if x.label == 'Confirm selected topics').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['chosen_topics'], ['Balcony gardening', 'Cooking on a budget'])
        self.assertTrue(any('No search has run' in x.value for x in app.info))
        next(x for x in app.text_area if x.label == 'Interests').set_value('Python')
        app.button[0].click().run()
        self.assertFalse('chosen_topics' in app.session_state)
        self.assertFalse(app.exception)

    def test_resume_only_requires_reviewed_fields(self):
        app = AppTest.from_file(APP).run()
        next(x for x in app.text_area if x.label.startswith('Resume')).set_value('Some profile text')
        app.button[0].click().run()
        self.assertFalse('creator_profile' in app.session_state)
        self.assertTrue(any('not automatically extracted' in w.value for w in app.warning))

    def test_select_and_edit_suggested_topic(self):
        app = AppTest.from_file(APP).run()
        app.text_area[0].set_value('Gardening')
        app.button[0].click().run()
        app.session_state['topic_editor_1'] = {
            'edited_rows': {0: {'Select': True, 'Topic': 'Gardening in small spaces'}},
            'added_rows': [], 'deleted_rows': [],
        }
        next(x for x in app.button if x.label == 'Confirm selected topics').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['chosen_topics'], ['Gardening in small spaces'])

    @patch('creator_compass.data.load_dataset', side_effect=ConnectionError('test network failure'))
    def test_dataset_failure_keeps_ui_working(self, load):
        app = AppTest.from_file(APP).run()
        next(x for x in app.button if x.label == 'Load / retry dataset sample').click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any('Dataset access failed' in e.value for e in app.error))


if __name__ == '__main__':
    unittest.main()
