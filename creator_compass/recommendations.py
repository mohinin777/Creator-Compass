"""Evidence-gated concepts and explicit, adjustable heuristic scoring."""
from hashlib import sha256
import json

from creator_compass.classification import CATEGORIES, validate_classifications
from creator_compass.discovery import search_videos, group_creators

DIMENSIONS = ['Creator fit', 'Search interest', 'Sampled competition', 'Audience evidence', 'Production feasibility']


def evidence_signature(bundle):
    classification = bundle.get('classification', {})
    return sha256(json.dumps([bundle['context'], bundle['sample'].revision,
        classification.get('scope'), classification.get('rows')], default=str, sort_keys=True).encode()).hexdigest()


def build_need(bundle, label, audience, identities, coverage_note):
    classification = bundle.get('classification')
    if not classification:
        raise ValueError('Classify or manually review comments first.')
    originals = {r['comment_id']: r for r in bundle['sample'].records}
    selected = [originals[i] for i in classification['scope'] if i in originals]
    rows = validate_classifications(classification['rows'], selected)
    valid = {r['comment_id']: r for r in rows if r['category'] != CATEGORIES[-1]}
    if not label.strip() or not audience.strip() or not coverage_note.strip():
        raise ValueError('Describe the specific need, intended audience, and observed coverage limits.')
    ids = list(dict.fromkeys(identities))
    if any(i not in valid for i in ids):
        raise ValueError('Choose only reviewed request comments in the current subset.')
    evidence = [{**originals[i], 'quote': valid[i]['quote'], 'category': valid[i]['category']} for i in ids]
    if len({r['video_id'] for r in evidence}) < 2:
        raise ValueError('A channel concept needs supporting requests from at least two distinct sampled videos. Keep single-video requests for further research.')
    return {'signature': evidence_signature(bundle), 'topic': bundle['context'][0],
            'need': label.strip(), 'audience': audience.strip(), 'coverage_note': coverage_note.strip(),
            'evidence': evidence, 'revision': bundle['sample'].revision}


def weighted_score(components, weights):
    available = [(components[name], weights.get(name, 0)) for name in DIMENSIONS
                 if components.get(name) is not None and weights.get(name, 0) > 0]
    denominator = sum(weight for _, weight in available)
    return round(sum(value * weight for value, weight in available) / denominator, 3) if denominator else None


def score_concept(need, profile, catalog, fit, effort_hours, trend=None):
    """Scores are on 0–5. Unknowns stay None and do not enter the denominator."""
    matches = search_videos(catalog.records, need['topic'], max(1, len(catalog.records)))
    channels = len(group_creators(matches))
    distinct = len({r['video_id'] for r in need['evidence']})
    hours = profile.get('hours')
    components = {
        'Creator fit': float(fit) if fit is not None else None,
        'Search interest': trend / 20 if trend is not None else None,
        'Sampled competition': 5 / (1 + channels) if channels else None,
        'Audience evidence': min(5, distinct),
        'Production feasibility': min(5, 5 * hours / effort_hours) if hours and effort_hours else None,
    }
    return components, channels
