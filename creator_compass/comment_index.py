"""A reusable, revision-specific SQLite index built by exhausting the comment split."""
from datetime import date, datetime
from contextlib import closing
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import tempfile

FIELDS = ('comment_id', 'video_id', 'text', 'published_at', 'like_count', 'reply_count')


def index_path(directory, revision):
    digest = sha256(('comments-v1:' + revision).encode()).hexdigest()
    return Path(directory) / f'index-{digest}.sqlite'


def build_index(records, directory, revision, split, progress=None):
    """Publish only a complete index; failures leave no usable partial database."""
    path = index_path(directory, revision)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return path
    with tempfile.NamedTemporaryFile(dir=path.parent, suffix='.sqlite', delete=False) as temporary:
        pending = Path(temporary.name)
    connection = None
    try:
        connection = sqlite3.connect(pending)
        connection.execute('CREATE TABLE comments (comment_id TEXT PRIMARY KEY, video_id TEXT NOT NULL, position INTEGER NOT NULL, payload TEXT NOT NULL)')
        connection.execute('CREATE TABLE metadata (revision TEXT, split TEXT, scanned INTEGER)')
        batch = []
        scanned = 0
        for scanned, row in enumerate(records, 1):
            identity, video, text = row.get('comment_id'), row.get('video_id'), row.get('text')
            if all(isinstance(value, str) and value.strip() for value in (identity, video, text)):
                evidence = {key: row.get(key) for key in FIELDS}
                timestamp = evidence['published_at']
                if isinstance(timestamp, (date, datetime)):
                    evidence['published_at'] = timestamp.isoformat()
                batch.append((identity, video, scanned, json.dumps(evidence)))
            if len(batch) >= 2000:
                connection.executemany('INSERT OR IGNORE INTO comments VALUES (?, ?, ?, ?)', batch)
                batch.clear()
            if progress and scanned % 10000 == 0:
                progress(scanned)
        if batch:
            connection.executemany('INSERT OR IGNORE INTO comments VALUES (?, ?, ?, ?)', batch)
        connection.execute('CREATE INDEX video_order ON comments (video_id, position)')
        connection.execute('INSERT INTO metadata VALUES (?, ?, ?)', (revision, split, scanned))
        connection.commit()
        connection.close()
        connection = None
        pending.replace(path)
        if progress:
            progress(scanned)
        return path
    finally:
        if connection is not None:
            connection.close()
        pending.unlink(missing_ok=True)
        Path(str(pending) + '-journal').unlink(missing_ok=True)


def query_index(path, video_ids, per_video, revision):
    # Read-only connections and bound parameters; no user strings become SQL.
    with closing(sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)) as connection:
        metadata = connection.execute('SELECT revision, split, scanned FROM metadata').fetchone()
        if metadata is None or metadata[0] != revision:
            raise ValueError('Comment index revision metadata does not match the requested dataset.')
        rows = []
        for identity in sorted(set(video_ids)):
            rows.extend(connection.execute(
                'SELECT position, payload FROM comments WHERE video_id = ? ORDER BY position LIMIT ?',
                (identity, per_video)).fetchall())
    rows.sort(key=lambda row: row[0])
    return metadata[1], metadata[2], [json.loads(payload) for _, payload in rows]
