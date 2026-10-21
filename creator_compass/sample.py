"""Inspect a bounded real sample: python -m creator_compass.sample --configuration videos."""
import argparse
import json
import sys

from creator_compass.data import load_development_subset


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--configuration', choices=['videos', 'comments'], default='videos')
    parser.add_argument('--limit', type=int, default=10)
    parser.add_argument('--split', default=None)
    args = parser.parse_args()
    try:
        sample = load_development_subset(args.limit, args.split, args.configuration)
    except Exception as exc:
        print(f'Dataset loading failed ({type(exc).__name__}). Check Hugging Face and file-host network access. No fallback data was loaded.', file=sys.stderr)
        return 1
    print(json.dumps({'configuration': sample.configuration, 'split': sample.split,
                      'available_splits': sample.available_splits, 'count': len(sample.records),
                      'columns': sample.columns, 'candidate_fields': sample.fields,
                      'first_record': sample.records[0] if sample.records else None},
                     indent=2, default=str))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
