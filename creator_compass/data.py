"""Bounded access to the selected dataset; never substitutes demonstration data."""
from dataclasses import dataclass
from typing import Any

from datasets import load_dataset

DATASET_ID = "brianhliou/youtube-comment-exposure"


@dataclass
class DevelopmentSample:
    configuration: str
    split: str
    available_splits: list[str]
    records: list[dict[str, Any]]
    columns: list[str]
    fields: dict[str, list[str]]


FIELD_NAMES = {
    "video identifier": ("video_id", "videoid", "youtube_id"),
    "video title": ("title", "video_title"),
    "creator identifier": ("channel_id", "channel", "channel_name", "channel_handle", "creator_id"),
    "comment text": ("comment", "text", "comment_text", "content"),
    "source link": ("url", "video_url", "youtube_url"),
    "category": ("category", "category_id", "tags"),
    "observed metrics": ("view_count", "like_count", "comment_count", "reply_count", "collected_comments"),
}


def identify_fields(columns: list[str]) -> dict[str, list[str]]:
    """Report observed candidate columns, without asserting their semantics."""
    return {role: [c for c in columns if c.lower() in names]
            for role, names in FIELD_NAMES.items()}


def load_development_subset(limit: int = 50, split: str | None = None,
                            configuration: str = 'videos') -> DevelopmentSample:
    if not 1 <= limit <= 200:
        raise ValueError("Development sample size must be between 1 and 200.")
    # Streaming bounds record materialization and avoids downloading the full corpus.
    # The repository exposes two configs, 'videos' and 'comments'; no default exists.
    if configuration not in ('videos', 'comments'):
        raise ValueError("Choose the videos or comments configuration.")
    dataset = load_dataset(DATASET_ID, configuration, streaming=True)
    splits = list(dataset.keys())
    if not splits:
        raise ValueError("The dataset exposes no splits.")
    selected = split if split is not None else splits[0]
    if selected not in splits:
        raise ValueError(f"Unknown split {selected!r}; available splits: {splits}")
    records = list(dataset[selected].take(limit))
    columns = list(dict.fromkeys(key for row in records for key in row))
    return DevelopmentSample(configuration, selected, splits, records, columns, identify_fields(columns))


@dataclass
class VideoCatalog:
    split: str
    records: list[dict[str, Any]]
    complete: bool


def load_video_catalog(max_records: int = 5000) -> VideoCatalog:
    """Load the small video metadata table, never the full comment corpus.

    One extra row distinguishes an exhausted split from a truncated prefix.
    """
    if not 1 <= max_records <= 10000:
        raise ValueError('Video catalog limit must be between 1 and 10000.')
    dataset = load_dataset(DATASET_ID, 'videos', streaming=True)
    splits = list(dataset.keys())
    if not splits:
        raise ValueError('The video configuration exposes no splits.')
    split = splits[0]
    rows = list(dataset[split].take(max_records + 1))
    return VideoCatalog(split, rows[:max_records], len(rows) <= max_records)
