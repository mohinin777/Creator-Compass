"""Comment sampling, explicit LLM actions, and human evidence review."""
from pathlib import Path
import os
from urllib.parse import urlencode

import pandas as pd
import streamlit as st

from creator_compass.classification import (
    CATEGORIES, UNREVIEWED, aggregate_categories, classify_comments,
    llm_configured, validate_classifications,
)
from creator_compass.comments import load_comment_sample
from creator_compass.discovery import search_videos, video_url


def source_link(row):
    base = video_url(row.get('video_id'))
    return base + '&' + urlencode({'lc': row['comment_id']}) if base else None


def render_comment_analysis(chosen, catalog):
    st.session_state.active_comment_context = None
    st.session_state.active_comment_scope = None
    st.header('Comment analysis')
    if not chosen:
        st.warning('Select, edit or add topics and confirm them in step 2 before analysis.')
        return
    if catalog is None:
        st.info('Load the video catalog in Creator discovery first.')
        return
    topic = st.selectbox('Confirmed topic to analyze', chosen)
    matches = search_videos(catalog.records, topic, limit=30)
    videos = {row['record']['video_id']: row['record'] for row in matches
              if video_url(row['record'].get('video_id'))}
    if not videos:
        st.info('No matching videos with usable source IDs. Edit or choose another confirmed topic.')
        return
    selected = st.multiselect('Videos to sample (up to 30)', list(videos),
                              default=list(videos)[:10],
                              format_func=lambda identity: videos[identity]['title'],
                              max_selections=30, key=f'comment_videos_{topic}')
    quota = st.select_slider('Comments per video', options=[20, 30, 40, 50], value=20)
    scan_limit = st.selectbox('Maximum comments to scan', [10_000, 100_000, 500_000, 1_500_000], index=1)
    st.caption('Reads comments sequentially and retains the first usable comments per selected video. This is a biased prefix sample, not a random sample. A scan may find few or no comments for later videos. Larger scans can be slow; only bounded samples are saved locally for reuse, keyed by dataset revision. No comments are sent to an LLM while sampling.')
    context = (topic, tuple(sorted(selected)), quota, scan_limit)
    st.session_state.active_comment_context = context
    if st.button('Sample real comments', disabled=not selected):
        with st.spinner('Scanning the selected dataset for comment evidence…'):
            try:
                sample = load_comment_sample(selected, quota, scan_limit,
                    cache_dir=str(Path(__file__).resolve().parents[1] / '.cache' / 'comment_samples'))
                st.session_state.comment_bundle = {'context': context, 'sample': sample}
                st.session_state.pop('comment_error', None)
                st.session_state.pop('classification_error', None)
            except Exception as exc:
                st.session_state.pop('comment_bundle', None)
                st.session_state.comment_error = f'Comment sampling failed ({type(exc).__name__}). Check dataset access and retry. No fallback comments were loaded.'
    if st.session_state.get('comment_error'):
        st.error(st.session_state.comment_error)
    bundle = st.session_state.get('comment_bundle')
    if not bundle or bundle['context'] != context:
        st.info('Sample comments for these settings before analysis. Previous samples are not used for changed topics or settings.')
        return
    sample = bundle['sample']
    st.write(f'Retained {len(sample.records)} comments after scanning {sample.scanned:,} records. Stop reason: {sample.stop_reason}.')
    st.caption(f'Dataset revision: {sample.revision} · comments split: {sample.split}')
    st.dataframe(pd.DataFrame(sample.coverage()), hide_index=True)
    if any(row['sampled_comments'] < quota for row in sample.coverage()):
        st.warning('Some videos have fewer comments than requested in this scan. Missing samples are unknown coverage, not evidence of absent viewer needs.')
    if not sample.records:
        return
    with st.expander('Inspect original sampled comments and sources', expanded=True):
        st.dataframe(pd.DataFrame([{**row, 'Source': source_link(row)} for row in sample.records]),
                     hide_index=True, column_config={'Source': st.column_config.LinkColumn('Source comment')})
    count = st.number_input('Comments to classify / review from this sample', min_value=1,
                            max_value=min(100, len(sample.records)), value=min(50, len(sample.records)))
    comments = sample.records[:int(count)]
    scope = tuple(row['comment_id'] for row in comments)
    st.session_state.active_comment_scope = scope
    st.caption(f'Classification covers the first {len(comments)} retained comments only; it may cover fewer videos than the full sample. At most 25 comments per API request, with each text capped at 4,000 characters. Original evidence remains available above.')
    if not llm_configured():
        st.info('LLM classification needs LLM_API_KEY2 in environment settings. Default: OpenAI gpt-4.1-nano. You can review comments manually below without an API key.')
    st.caption('The LLM button sends only these comment IDs and text to the configured provider and may incur charges. Creator profile and resume text are not sent.')
    if st.button('Classify sampled comments with LLM', disabled=not llm_configured()):
        with st.spinner('Classifying bounded batches and checking source evidence…'):
            try:
                rows = classify_comments(comments)
                bundle['classification'] = {'scope': scope, 'rows': rows, 'method': f"LLM ({os.environ.get('LLM_MODEL', 'gpt-4.1-nano')}) — review required"}
                st.session_state.pop('classification_error', None)
            except Exception as exc:
                st.session_state.classification_error = str(exc)
    if st.session_state.get('classification_error'):
        st.error(st.session_state.classification_error)
    classification = bundle.get('classification')
    valid = classification and classification['scope'] == scope
    existing = {r['comment_id']: r for r in classification['rows']} if valid else {}
    with st.expander('Manual categorization / review'):
        st.caption('Select a category for every displayed comment. For requests, paste an exact supporting excerpt into Quote. Unreviewed rows are never counted as general feedback.')
        with st.form('manual_comment_review'):
            reviewed = st.data_editor(pd.DataFrame([{
                'comment_id': row['comment_id'], 'Text': row['text'],
                'category': existing.get(row['comment_id'], {}).get('category', UNREVIEWED),
                'quote': existing.get(row['comment_id'], {}).get('quote', ''),
            } for row in comments]), hide_index=True, disabled=['comment_id', 'Text'],
                column_config={'category': st.column_config.SelectboxColumn('Category', options=[UNREVIEWED] + CATEGORIES)},
                key='review_' + str(hash((context, scope, repr(existing)))))
            save = st.form_submit_button('Save reviewed categories')
        if save:
            try:
                rows = validate_classifications(reviewed.to_dict('records'), comments)
                bundle['classification'] = {'scope': scope, 'rows': rows, 'method': 'Human reviewed'}
                st.session_state.pop('classification_error', None)
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
    if not valid:
        st.info('No validated classifications for this subset yet. No audience-gap findings have been produced.')
        return
    st.subheader('Evidence by request category')
    st.caption(f"Method: {classification['method']}. Counts cover only {len(comments)} classified comments. Category recurrence does not establish the same unmet need or missing coverage in the video.")
    summaries = aggregate_categories(comments, classification['rows'])
    st.table([{k: v for k, v in summary.items() if k != 'evidence'} for summary in summaries])
    originals = {row['comment_id']: row for row in comments}
    for summary in summaries:
        with st.expander(summary['category']):
            for evidence in summary['evidence']:
                st.text(evidence['quote'] or originals[evidence['comment_id']]['text'])
                st.caption(f"Video {evidence['video_id']} · comment {evidence['comment_id']}")
                link = source_link(originals[evidence['comment_id']])
                if link:
                    st.link_button('Source comment', link)
            if summary['category'] != CATEGORIES[-1] and summary['distinct_videos'] >= 2:
                st.info('Possible angle to investigate: address this request category. Review the specific excerpts and existing video coverage before treating it as a differentiation hypothesis. A shared category alone is not a proven content gap.')
    st.caption('These static, self-selected comments are not representative of all viewers. No opportunity scores or channel recommendations are calculated here.')
