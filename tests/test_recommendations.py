import unittest
from creator_compass.comments import CommentSample
from creator_compass.data import VideoCatalog
from creator_compass.classification import CATEGORIES
from creator_compass.recommendations import build_need, score_concept, weighted_score


def fixture():
    comments = [dict(comment_id='c1', video_id='aaaaaaaaaaa', text='Please show examples'),
                dict(comment_id='c2', video_id='bbbbbbbbbbb', text='More examples please')]
    sample = CommentSample('rev', 'train', ['aaaaaaaaaaa', 'bbbbbbbbbbb'], 20, 10000, 2, 'split exhausted', comments)
    return {'sample': sample, 'context': ('Gardening', ('aaaaaaaaaaa', 'bbbbbbbbbbb'), 20, 10000),
            'classification': {'scope': ('c1', 'c2'), 'method': 'Human reviewed', 'rows': [
                dict(comment_id='c1', category=CATEGORIES[1], quote='show examples'),
                dict(comment_id='c2', category=CATEGORIES[1], quote='More examples')]}}


class RecommendationTests(unittest.TestCase):
    def test_evidence_gate_and_source_retention(self):
        bundle = fixture()
        with self.assertRaises(ValueError):
            build_need(bundle, 'Examples', 'Beginners', ['c1'], 'Title coverage is uncertain')
        need = build_need(bundle, 'Examples', 'Beginners', ['c1', 'c2'], 'Title coverage is uncertain')
        self.assertEqual(need['revision'], 'rev')
        self.assertEqual(need['evidence'][1]['quote'], 'More examples')
        with self.assertRaises(ValueError):
            build_need(bundle, 'Examples', 'Beginners', ['invented'], 'Unknown')

    def test_unknown_dimensions_and_adjustable_weights(self):
        need = build_need(fixture(), 'Examples', 'Beginners', ['c1','c2'], 'Unknown coverage')
        catalog = VideoCatalog('train', [{'title': 'Gardening examples', 'video_id': 'aaaaaaaaaaa', 'channel_handle': '@one'}], True)
        components, count = score_concept(need, {'hours': 4}, catalog, 4, 8)
        self.assertIsNone(components['Search interest'])
        self.assertEqual(components['Audience evidence'], 2)
        self.assertEqual(components['Production feasibility'], 2.5)
        self.assertEqual(count, 1)
        self.assertEqual(weighted_score(components, {'Creator fit': 1, 'Search interest': 5}), 4)
        self.assertEqual(weighted_score(components, {'Audience evidence': 1}), 2)
        self.assertIsNone(weighted_score(components, {'Search interest': 1}))
        self.assertIsNone(weighted_score(components, {}))


class RecommendationUITests(unittest.TestCase):
    def test_manual_evidence_to_idea_weights_and_stale_scope(self):
        from streamlit.testing.v1 import AppTest
        from pathlib import Path
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'))
        app.session_state['creator_profile'] = {'hours': 4, 'interests': 'Gardening'}
        app.session_state['chosen_topics'] = ['Gardening']
        app.session_state['comment_bundle'] = fixture()
        app.session_state['video_catalog'] = VideoCatalog('train', [
            {'video_id': 'aaaaaaaaaaa', 'title': 'Gardening basics', 'channel_handle': '@one'},
            {'video_id': 'bbbbbbbbbbb', 'title': 'Gardening examples', 'channel_handle': '@two'}], True)
        app.run()
        next(x for x in app.checkbox if x.label == 'Use a quick limited scan instead of the full dataset').check().run()
        next(x for x in app.selectbox if x.label == 'Maximum comments to scan').set_value(10000).run()
        self.assertFalse(app.exception)
        next(x for x in app.text_input if x.label == 'Specific viewer need').set_value('Hands-on gardening examples')
        next(x for x in app.text_input if x.label == 'Intended audience').set_value('Beginning gardeners')
        next(x for x in app.multiselect if x.label == 'Supporting request comment IDs').set_value(['c1', 'c2'])
        next(x for x in app.text_area if x.label == 'Observed coverage and limits').set_value('Titles mention basics and examples; full coverage remains uncertain.')
        next(x for x in app.button if x.label == 'Save supported channel hypothesis').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.session_state['channel_needs']), 1)
        self.assertEqual(len(app.metric), 1)
        self.assertTrue(any('Trend data unavailable' in x.value for x in app.caption))
        for slider in app.slider:
            if slider.label.endswith(' weight'):
                slider.set_value(1 if slider.label == 'Audience evidence weight' else 0)
        app.run()
        self.assertEqual(app.metric[0].value, '2.00 / 5')
        next(x for x in app.number_input if x.label == 'Comments to classify / review from this sample').set_value(1).run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.metric), 0)
