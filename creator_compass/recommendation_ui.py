"""Human-reviewed differentiation hypotheses and transparent decision aids."""
import json
import streamlit as st

from creator_compass.classification import CATEGORIES
from creator_compass.comment_ui import source_link
from creator_compass.recommendations import DIMENSIONS, build_need, evidence_signature, score_concept, weighted_score


def render_recommendations(chosen, profile, catalog):
    st.header('Channel ideas and opportunity scorecard')
    st.caption('Concepts below are local templates based on your reviewed hypotheses, not LLM-generated market findings. Scores are decision aids, not predictions of success.')
    bundle = st.session_state.get('comment_bundle')
    if not chosen or not profile or catalog is None:
        st.info('Save a profile, confirm topics, and load discovery before building channel ideas.')
        return
    if not bundle or bundle['context'][0] not in chosen or not bundle.get('classification'):
        st.info('First sample and classify comments in step 4, using manual review or the optional LLM.')
        return
    classification = bundle['classification']
    # Do not use evidence from a different active sampling or review scope.
    if (bundle['context'] != st.session_state.get('active_comment_context')
            or tuple(classification['scope']) != st.session_state.get('active_comment_scope')):
        st.warning('Comment settings changed. Sample and review the current subset before generating ideas.')
        return
    signature = evidence_signature(bundle)
    requests = {r['comment_id']: r for r in classification['rows'] if r['category'] != CATEGORIES[-1]}
    originals = {r['comment_id']: r for r in bundle['sample'].records}
    if len({originals[i]['video_id'] for i in requests}) < 2:
        st.warning('There are not yet supporting request comments from two distinct videos. Review more matching videos before proposing an evidence-backed channel idea. No recommendations or zero evidence scores are invented.')
        return
    st.subheader('Review a specific audience need')
    st.caption('A shared category does not mean the same need. Choose excerpts expressing one specific need; compare the linked titles and video coverage yourself. Save up to three distinct hypotheses. Two or three ideas appear only when you can support them.')
    for identity, row in requests.items():
        with st.expander(identity):
            st.text(row['quote'])
            video = originals[identity]['video_id']
            record = next((r for r in catalog.records if r.get('video_id') == video), {})
            st.write('Observed video title:', record.get('title', 'Unavailable'))
            link = source_link(originals[identity])
            if link:
                st.link_button('Inspect source and coverage', link)
    with st.form('need_hypothesis'):
        label = st.text_input('Specific viewer need', placeholder='Describe the shared question or request in these excerpts')
        audience = st.text_input('Intended audience', placeholder='Who would benefit? This is your hypothesis.')
        ids = st.multiselect('Supporting request comment IDs', list(requests))
        coverage = st.text_area('Observed coverage and limits', placeholder='What do the actual titles/videos cover? What remains uncertain? Do not infer missing coverage from a request alone.')
        save = st.form_submit_button('Save supported channel hypothesis')
    needs = [n for n in st.session_state.get('channel_needs', []) if n['signature'] == signature]
    if save:
        try:
            need = build_need(bundle, label, audience, ids, coverage)
            if any(n['need'].casefold() == need['need'].casefold() or set(r['comment_id'] for r in n['evidence']) == set(ids) for n in needs):
                raise ValueError('This need or identical evidence set is already saved. Add genuinely distinct supported needs.')
            if len(needs) >= 3:
                raise ValueError('Three hypotheses are already saved; clear them to revise.')
            needs.append(need)
            st.session_state.channel_needs = needs
            st.success('Supported hypothesis saved.')
        except ValueError as exc:
            st.error(str(exc))
    if not needs:
        return
    if st.button('Clear channel hypotheses'):
        st.session_state.channel_needs = []
        st.rerun()
    st.subheader('Adjust scoring weights')
    weights = {name: st.slider(name + ' weight', 0, 5, 1, key='weight_' + name) for name in DIMENSIONS}
    st.caption('Each dimension is 0–5. Weighted score = Σ(available dimension × weight) / Σ(available weights). Missing dimensions and zero weights are excluded. All-zero weights produce an unknown score.')
    output = []
    for index, need in enumerate(needs):
        with st.container(border=True):
            st.subheader(f"{index + 1}. {need['topic']}: {need['need']}")
            st.write('Channel concept:', f"A {', '.join(profile.get('styles', [])) or 'practical explanation'} channel about {need['topic']}, addressing {need['need']} for {need['audience']}.")
            st.write('Target audience (your hypothesis):', need['audience'])
            st.write('Possible differentiation:', need['need'])
            st.write('Coverage review (your assessment):', need['coverage_note'])
            st.write('Profile evidence:', {k: profile.get(k) for k in ['interests', 'skills', 'expertise', 'styles', 'budget', 'camera', 'constraints']})
            fit = st.slider('Creator fit — your assessment', 0, 5, 3, key=f'fit_{signature}_{index}')
            fit_reason = st.text_input('Why this fits your stated strengths', key=f'fit_reason_{signature}_{index}')
            effort = st.number_input('Estimated weekly production hours for this idea', min_value=1, max_value=160, value=5, key=f'effort_{signature}_{index}')
            has_trend = st.checkbox('I have actual relative search-interest observations', key=f'trend_yes_{signature}_{index}')
            trend, trend_source = None, ''
            if has_trend:
                value = st.number_input('Observed relative search interest (0–100)', 0, 100, 50, key=f'trend_value_{signature}_{index}')
                trend_source = st.text_input('Trend source, search term, region and observation period', key=f'trend_source_{signature}_{index}')
                if trend_source.strip():
                    trend = value
                else:
                    st.warning('Describe the observation source and scope before including trend data.')
            if trend is None:
                st.caption('Trend data unavailable — excluded from scoring.')
            components, channels = score_concept(need, profile, catalog, fit if fit_reason.strip() else None, effort, trend)
            explanations = {
                'Creator fit': fit_reason.strip() or 'Unknown until you explain your fit assessment against the profile above.',
                'Search interest': 'Your observed value / 20, for the declared source/scope; relative interest is not forecast views.',
                'Sampled competition': f'5 / (1 + {channels} matching dataset channels). Fewer sampled matches increase this heuristic; this is not YouTube-wide competition.',
                'Audience evidence': f'min(5, {len(set(r["video_id"] for r in need["evidence"]))} supporting distinct videos). It measures recurrence, not proof of unmet demand.',
                'Production feasibility': f'min(5, 5 × {profile.get("hours")} available weekly hours / {effort} estimated required hours). Budget and format constraints still need judgment.',
            }
            st.table([{'Dimension': name, 'Value': f'{components[name]:.3f}' if components[name] is not None else 'Unknown', 'Calculation and evidence': explanations[name]} for name in DIMENSIONS])
            score = weighted_score(components, weights)
            st.metric('Partial opportunity score' if any(value is None for value in components.values()) else 'Opportunity score', f'{score:.2f} / 5' if score is not None else 'Unknown')
            st.caption('Heuristic only. Reviewers can disagree with the inputs. Small or lexically narrow samples can distort both competition and audience-evidence values.')
            for evidence in need['evidence']:
                st.text(evidence['quote'])
                link = source_link(evidence)
                if link:
                    st.link_button('Supporting source comment', link, key=f'source_{index}_{evidence["comment_id"]}')
            output.append({'concept': need, 'components': components, 'weights': weights, 'score': score, 'fit_reason': fit_reason, 'estimated_production_hours': effort, 'trend_source': trend_source})
    ranked = sorted(output, key=lambda row: (row['score'] is None, -(row['score'] or 0)))
    st.subheader('Current ranking')
    st.table([{'Concept': row['concept']['need'], 'Score / 5': f"{row['score']:.3f}" if row['score'] is not None else 'Unknown'} for row in ranked])
    st.download_button('Download evidence and scorecard (JSON)', json.dumps(ranked, indent=2, default=str), file_name='creator-compass-ideas.json', mime='application/json')
