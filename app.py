"""Run with: python -m streamlit run app.py."""
import pandas as pd
import streamlit as st

from creator_compass.data import DATASET_ID, load_development_subset, load_video_catalog
from creator_compass.discovery import search_videos, group_creators, terms
from creator_compass.comment_ui import render_comment_analysis
from creator_compass.recommendation_ui import render_recommendations
from creator_compass.topics import selected_topics, suggest_topics

st.set_page_config(page_title='Creator Compass', page_icon='🧭', layout='wide')
st.title('🧭 Creator Compass')
st.caption('Turn your experience into topics worth investigating. First working version.')
st.info('Build your profile, confirm topics, discover videos, review viewer requests, and compare supported channel ideas. API automation is optional.')

profile_tab, topics_tab, data_tab, discovery_tab, comments_tab, recommendations_tab = st.tabs([
    '1 · Creator profile', '2 · Choose topics', 'Dataset sample',
    '3 · Creator discovery', '4 · Comment analysis', '5 · Recommendations'])

with profile_tab:
    st.header('Your starting point')
    st.write('Enter interests and strengths directly, or paste profile text as a reference while completing the questionnaire.')
    with st.form('profile'):
        name = st.text_input('Name or creator alias (optional)')
        left, right = st.columns(2)
        with left:
            interests = st.text_area('Interests', placeholder='Gardening, personal finance, Python')
            skills = st.text_area('Skills', placeholder='Teaching, data analysis, storytelling')
            expertise = st.text_area('Personal or professional expertise', placeholder='Career experience, hobbies, lived experience')
        with right:
            styles = st.multiselect('Preferred content styles', ['Tutorials', 'Practical demonstrations', 'Explainers', 'Comparisons', 'Personal stories'])
            hours = st.number_input('Available production hours per week', min_value=1, max_value=80, value=5)
            budget = st.selectbox('Production budget', ['Minimal / existing equipment', 'Modest', 'Flexible'])
            camera = st.selectbox('On-camera preference', ['Either', 'Prefer on camera', 'Prefer voiceover / screen recording'])
            constraints = st.text_area('Other production constraints (optional)')
        resume = st.text_area('Resume or LinkedIn profile text (optional)', help='Paste text only. No scraping or automatic extraction in this version. Review it yourself and enter relevant strengths above.')
        st.caption('Profile text stays in this Streamlit session; this app does not send it to an LLM or write it to disk.')
        save = st.form_submit_button('Save profile and suggest topics')
    if save:
        profile = dict(name=name, interests=interests, skills=skills, expertise=expertise,
                       styles=styles, hours=hours, budget=budget, camera=camera,
                       constraints=constraints, resume=resume)
        if not any(value.strip() for value in (interests, skills, expertise)):
            st.warning('Add at least one interest, skill, or area of expertise. Pasted text is not automatically extracted.')
        else:
            changed = profile != st.session_state.get('creator_profile')
            st.session_state.creator_profile = profile
            if changed:
                st.session_state.suggestions = suggest_topics(profile)
                st.session_state.pop('chosen_topics', None)
                st.session_state['topic_revision'] = st.session_state.get('topic_revision', 0) + 1
            st.success('Profile saved. Open “2 · Choose topics” to review and select topics.')
    if 'creator_profile' in st.session_state:
        p = st.session_state.creator_profile
        st.subheader('Saved profile')
        st.write({k: v for k, v in p.items() if k != 'resume'})
        st.caption('Edit the questionnaire and save again to update your profile. Changes reset topic confirmation.')

with topics_tab:
    st.header('Choose what to investigate')
    st.caption('Suggestions use simple templates based on your entries. They are not LLM-generated or validated against market demand. Trend data unavailable.')
    if 'suggestions' not in st.session_state:
        st.info('Save your creator profile first.')
    else:
        suggestions = st.session_state.suggestions
        st.write('Review the topic cards, then select and edit rows below. Added topics are included when you confirm.')
        for start in range(0, len(suggestions), 2):
            for column, suggestion in zip(st.columns(2), suggestions[start:start+2]):
                with column.container(border=True):
                    st.markdown('**' + suggestion['topic'].replace('*', '') + '**')
                    st.caption(suggestion['reason'])
        with st.form('topic_selection'):
            table = st.data_editor(pd.DataFrame([{'Select': False, 'Topic': s['topic']} for s in suggestions]),
                                   hide_index=True, width='stretch',
                                   column_config={'Select': st.column_config.CheckboxColumn('Select', required=True)},
                                   key=f'topic_editor_{st.session_state.get("topic_revision", 0)}')
            added = st.text_area('Add your own topics (one per line)', key=f'added_{st.session_state.get("topic_revision", 0)}')
            confirm = st.form_submit_button('Confirm selected topics')
        if confirm:
            chosen = selected_topics(table.to_dict('records'), added)
            if not chosen:
                st.session_state.pop('chosen_topics', None)
                st.warning('Select or add at least one nonempty topic before continuing.')
            else:
                st.session_state.chosen_topics = chosen
                st.success('Topics confirmed. Open step 3 to discover relevant videos and creators.')
        if st.session_state.get('chosen_topics'):
            st.subheader('Confirmed topics')
            st.write(st.session_state.chosen_topics)
            st.caption('After editing topics, confirm again to update this list.')

@st.cache_data(ttl=3600, show_spinner=False)
def cached_sample(limit, configuration):
    return load_development_subset(limit=limit, configuration=configuration)

with data_tab:
    st.header('Real dataset development sample')
    st.write(f'Selected dataset: `{DATASET_ID}`')
    configuration = st.selectbox('Dataset configuration', ['videos', 'comments'])
    st.caption('Streaming reads at most the requested number of records from the first available split. This small, unshuffled prefix is not representative of all YouTube or the full dataset. No fabricated fallback records are used.')
    limit = st.number_input('Maximum sample records', min_value=1, max_value=200, value=50)
    if st.button('Load / retry dataset sample'):
        with st.spinner('Loading a bounded sample from Hugging Face…'):
            try:
                st.session_state.sample = cached_sample(int(limit), configuration)
                st.session_state.pop('dataset_error', None)
            except Exception as exc:
                st.session_state.pop('sample', None)
                st.session_state.dataset_error = f'{type(exc).__name__}: {exc}'
    if 'dataset_error' in st.session_state:
        st.error('Dataset access failed. Profile and topic selection remain available. Check Hugging Face network access and retry.')
        with st.expander('Technical error details'):
            st.code(st.session_state.dataset_error)
    if 'sample' in st.session_state:
        sample = st.session_state.sample
        st.success(f'Loaded {len(sample.records)} actual {sample.configuration} records from split {sample.split!r}.')
        st.write('Available splits:', sample.available_splits)
        st.write('Observed columns:', sample.columns)
        st.subheader('Candidate application fields')
        st.caption('Column-name matches only; field meaning still needs confirmation during implementation.')
        st.table([{'Needed field': role, 'Observed candidate columns': ', '.join(cols) or 'Unavailable / unrecognized'} for role, cols in sample.fields.items()])
        if sample.records:
            st.dataframe(pd.DataFrame(sample.records), hide_index=True)
            with st.expander('First actual record'):
                st.json(sample.records[0])
        else:
            st.warning('The selected split returned no records.')
    else:
        st.info('Load the sample to inspect real fields. No dataset records have been loaded in this session.')
    st.caption('Dataset license and reuse conditions govern caching or redistribution. Development samples on this screen stay in process memory; comment-analysis samples are cached locally for reuse.')

@st.cache_data(ttl=3600, show_spinner=False)
def cached_catalog():
    return load_video_catalog()

with discovery_tab:
    st.header('Creator discovery')
    chosen = st.session_state.get('chosen_topics', [])
    if not chosen:
        st.warning('Select, edit or add topics and confirm them in step 2 before analysis.')
    else:
        st.write('Confirmed research topics:', chosen)
        st.caption('Search uses title words only, with common template words removed. Exact word overlap can miss synonyms or videos whose titles omit a topic. Results describe this static dataset, not all of YouTube.')
        if st.button('Load video catalog and discover creators'):
            with st.spinner('Loading real video metadata…'):
                try:
                    st.session_state.video_catalog = cached_catalog()
                    st.session_state.pop('discovery_error', None)
                except Exception as exc:
                    st.session_state.pop('video_catalog', None)
                    st.session_state.discovery_error = f'{type(exc).__name__}: {exc}'
        if 'discovery_error' in st.session_state:
            st.error('Video catalog loading failed. Check dataset network access and retry; no fallback videos are shown.')
            with st.expander('Catalog error details'):
                st.code(st.session_state.discovery_error)
        catalog = st.session_state.get('video_catalog')
        if catalog is None:
            st.info('No search has run. Load the video catalog to search your confirmed topics.')
        else:
            st.caption(f'Source: {DATASET_ID} · videos · split {catalog.split} · {len(catalog.records)} metadata records. Cached in memory for one hour; no full comment download.')
            if not catalog.complete:
                st.warning('The catalog hit its safety limit. Coverage refers only to the loaded prefix, not the entire split.')
            if not catalog.records:
                st.warning('The video catalog is empty.')
            elif not any(isinstance(row.get('title'), str) and row['title'].strip() for row in catalog.records):
                st.warning('No usable video titles are available; title matching cannot run.')
            for topic in chosen:
                with st.expander(topic, expanded=True):
                    matches = search_videos(catalog.records, topic, limit=max(1, len(catalog.records)))
                    if not terms(topic):
                        st.warning('This topic has no searchable terms after removing common words. Edit it to include a specific subject.')
                    elif not matches:
                        st.warning('No title matches in the loaded dataset. This does not establish absent competition or an audience gap.')
                    else:
                        groups = group_creators(matches)
                        missing = sum(not isinstance(m['record'].get('channel_handle'), str) or not m['record']['channel_handle'].strip() for m in matches)
                        st.write(f'{len(matches)} matching videos · {len(groups)} identified channels')
                        if missing:
                            st.caption(f'{missing} matching videos lack a channel handle and are excluded from channel grouping.')
                        if groups:
                            st.subheader('Channels in these matches')
                            st.dataframe(pd.DataFrame(groups).rename(columns={'channel_handle': 'Channel', 'matched_videos': 'Matched videos', 'best_relevance': 'Best title relevance'}), hide_index=True)
                        st.caption('Showing up to 20 videos. Title relevance is matched query-word weight / total query-word weight, with rarer words weighted more. It is not a success or opportunity score. Partial matches need review.')
                        rows = []
                        for match in matches[:20]:
                            record = match['record']
                            rows.append({
                                'Title': record.get('title'), 'Channel': record.get('channel_handle'),
                                'Title relevance': round(match['relevance'], 3),
                                'Matched words': ', '.join(match['matched_terms']),
                                'Query words': ', '.join(match['query_terms']),
                                'Source': match['source_url'],
                                'Recorded views': record.get('view_count'),
                                'Recorded likes': record.get('like_count'),
                                'Recorded comments': record.get('comment_count'),
                                'Stats fetched at': record.get('stats_fetched_at'),
                            })
                        st.dataframe(pd.DataFrame(rows), hide_index=True, column_config={'Source': st.column_config.LinkColumn('YouTube source')})
                        st.caption('Source links are constructed from observed valid video IDs. Metrics are recorded dataset observations, not live counts. Blank values are unavailable.')

with comments_tab:
    render_comment_analysis(st.session_state.get('chosen_topics', []), st.session_state.get('video_catalog'))

with recommendations_tab:
    render_recommendations(st.session_state.get('chosen_topics', []),
                           st.session_state.get('creator_profile'),
                           st.session_state.get('video_catalog'))
