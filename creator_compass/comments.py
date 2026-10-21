"""Full-split indexing by default, plus optional bounded streaming samples."""
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date, datetime
from hashlib import sha256
import json
from pathlib import Path
import tempfile
from typing import Iterable

from datasets import load_dataset
from huggingface_hub import HfApi

from creator_compass.data import DATASET_ID
from creator_compass.discovery import video_url
from creator_compass.comment_index import index_path, build_index, query_index


@dataclass
class CommentSample:
    revision: str
    split: str
    video_ids: list[str]
    per_video: int
    max_scan: int | None
    scanned: int
    stop_reason: str
    records: list[dict]

    def coverage(self):
        counts = Counter(row['video_id'] for row in self.records)
        return [{'video_id': identity, 'sampled_comments': counts[identity],
                 'target_comments': self.per_video} for identity in self.video_ids]


def sample_records(records: Iterable[dict], video_ids: list[str], per_video: int,
                   max_scan: int, revision: str, split: str) -> CommentSample:
    ids = sorted(set(video_ids))
    if not 1 <= len(ids) <= 30 or any(video_url(i) is None for i in ids):
        raise ValueError('Choose 1–30 valid observed video IDs.')
    if not 1 <= per_video <= 50 or not 1 <= max_scan <= 1_500_000:
        raise ValueError('Choose 1–50 comments/video and a scan limit of 1–1,500,000.')
    counts = Counter()
    retained, seen = [], set()
    scanned = 0
    stop = 'split exhausted'
    iterator = iter(records)
    while scanned < max_scan:
        try:
            row = next(iterator)
        except StopIteration:
            break
        scanned += 1
        identity, comment_id, text = row.get('video_id'), row.get('comment_id'), row.get('text')
        if (identity not in ids or counts[identity] >= per_video
                or not isinstance(comment_id, str) or not comment_id.strip()
                or not isinstance(text, str) or not text.strip() or comment_id in seen):
            continue
        seen.add(comment_id)
        # Retain evidence fields, not author identifiers or unrelated raw columns.
        evidence = {key: row.get(key) for key in (
            'comment_id', 'video_id', 'text', 'published_at', 'like_count', 'reply_count')}
        if isinstance(evidence['published_at'], (datetime, date)):
            evidence['published_at'] = evidence['published_at'].isoformat()
        retained.append(evidence)
        counts[identity] += 1
        if all(counts[i] >= per_video for i in ids):
            stop = 'all sample targets reached'
            break
    else:
        stop = 'scan limit reached'
    return CommentSample(revision, split, ids, per_video, max_scan, scanned, stop, retained)


def load_comment_sample(video_ids: list[str], per_video: int = 20,
                        max_scan: int | None = None, cache_dir: str | None = None,
                        progress=None) -> CommentSample:
    if not 1 <= len(set(video_ids)) <= 30 or any(video_url(i) is None for i in video_ids):
        raise ValueError('Choose 1–30 valid observed video IDs.')
    if not 1 <= per_video <= 50:
        raise ValueError('Choose 1–50 retained comments per video.')
    # Pin data and cache identity to an actual Hub commit, not the mutable main ref.
    revision = HfApi().dataset_info(DATASET_ID).sha
    if not revision:
        raise ValueError('Could not resolve dataset revision.')
    if max_scan is None:
        directory = cache_dir or str(Path.cwd() / '.cache' / 'comment_samples')
        path = index_path(directory, revision)
        if not path.exists():
            dataset = load_dataset(DATASET_ID, 'comments', revision=revision, streaming=True)
            splits = list(dataset.keys())
            if not splits:
                raise ValueError('The comments configuration exposes no splits.')
            path = build_index(dataset[splits[0]], directory, revision, splits[0], progress)
        split, scanned, rows = query_index(path, video_ids, per_video, revision)
        return CommentSample(revision, split, sorted(set(video_ids)), per_video, None,
                             scanned, 'full split indexed', rows)
    key_data = [1, DATASET_ID, revision, sorted(set(video_ids)), per_video, max_scan]
    key = sha256(json.dumps(key_data).encode()).hexdigest()
    path = Path(cache_dir) / f'{key}.json' if cache_dir else None
    if path and path.exists():
        return CommentSample(**json.loads(path.read_text()))
    dataset = load_dataset(DATASET_ID, 'comments', revision=revision, streaming=True)
    splits = list(dataset.keys())
    if not splits:
        raise ValueError('The comments configuration exposes no splits.')
    sample = sample_records(dataset[splits[0]], video_ids, per_video, max_scan, revision, splits[0])
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as file:
            temporary = Path(file.name)
            try:
                json.dump(asdict(sample), file)
            except Exception:
                temporary.unlink(missing_ok=True)
                raise
        temporary.replace(path)
    return sample
