"""Explainable lexical discovery over real video titles. No market estimates."""
from collections import Counter
from math import log
import re
from typing import Any

# Remove function words and the generic wording introduced by our topic templates.
STOP_WORDS = set('a an and are as at be by for from how in into is it of on or the to with your using through beginner beginners guide practical examples common mistakes'.split())


def terms(text: str) -> set[str]:
    normalized = re.sub(r"['’]s\b", '', text.casefold())
    return {word for word in re.findall(r'[^\W_]+', normalized)
            if word not in STOP_WORDS}


def video_url(video_id: Any) -> str | None:
    if isinstance(video_id, str) and re.fullmatch(r'[A-Za-z0-9_-]{11}', video_id):
        return f'https://www.youtube.com/watch?v={video_id}'
    return None


def search_videos(records: list[dict], topic: str, limit: int = 20) -> list[dict]:
    """Rank title overlaps by inverse-frequency-weighted query coverage.

    Nonmatching videos never appear. Scores are textual relevance, not opportunity.
    Duplicate video IDs are collapsed before counting and ranking.
    """
    if limit < 1:
        raise ValueError('Result limit must be positive.')
    query = terms(topic)
    if not query:
        return []
    unique = []
    seen = set()
    for row in records:
        title = row.get('title')
        if not isinstance(title, str) or not title.strip():
            continue
        identity = row.get('video_id')
        if identity and identity in seen:
            continue
        if identity:
            seen.add(identity)
        unique.append((row, terms(title)))
    counts = Counter(token for _, tokens in unique for token in tokens)
    weights = {token: 1 + log((len(unique) + 1) / (counts[token] + 1)) for token in query}
    denominator = sum(weights.values())
    results = []
    for row, tokens in unique:
        matched = query & tokens
        if not matched:
            continue
        results.append({
            'record': row,
            'matched_terms': sorted(matched),
            'query_terms': sorted(query),
            'relevance': sum(weights[t] for t in matched) / denominator,
            'source_url': video_url(row.get('video_id')),
        })
    return sorted(results, key=lambda result: (-result['relevance'], str(result['record'].get('title', ''))))[:limit]


def group_creators(results: list[dict]) -> list[dict]:
    """Group only by an observed nonempty channel handle, never comment authors."""
    groups = {}
    for result in results:
        handle = result['record'].get('channel_handle')
        if not isinstance(handle, str) or not handle.strip():
            continue
        handle = handle.strip()
        key = handle.casefold()
        if key not in groups:
            groups[key] = {'channel_handle': handle, 'matched_videos': 0, 'best_relevance': 0.0}
        groups[key]['matched_videos'] += 1
        groups[key]['best_relevance'] = max(groups[key]['best_relevance'], result['relevance'])
    return sorted(groups.values(), key=lambda row: (-row['matched_videos'], -row['best_relevance'], row['channel_handle']))
