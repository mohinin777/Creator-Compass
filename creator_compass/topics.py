"""Transparent, local topic prompts; no market or LLM claims."""
import re


def parse_entries(text: str) -> list[str]:
    return list(dict.fromkeys(part.strip() for part in re.split(r'[,\n]', text) if part.strip()))


def suggest_topics(profile: dict) -> list[dict[str, str]]:
    interests = parse_entries(profile.get('interests', ''))
    skills = parse_entries(profile.get('skills', ''))
    expertise = parse_entries(profile.get('expertise', ''))
    seeds = list(dict.fromkeys(interests + expertise + skills))[:4]
    styles = profile.get('styles', [])
    suggestions = []
    for seed in seeds:
        suggestions.extend([
            {'topic': f'{seed}: a beginner’s guide', 'reason': f'Based on your stated interest or experience in {seed}.'},
            {'topic': f'{seed}: practical examples and common mistakes', 'reason': f'A concrete starting angle for {seed}; audience demand is unverified.'},
        ])
    if seeds and skills:
        suggestions.append({'topic': f'Using {skills[0]} for {seeds[0]}',
                            'reason': 'Combines a stated skill with a profile topic.'})
    if seeds and styles:
        suggestions.append({'topic': f'{seeds[0]} through {styles[0].lower()}',
                            'reason': 'Uses your preferred content style.'})
    return list({s['topic'].casefold(): s for s in suggestions}.values())


def selected_topics(rows: list[dict], added: str = '') -> list[str]:
    chosen = [str(row.get('Topic', '')).strip() for row in rows if row.get('Select')]
    chosen += [line.strip() for line in added.splitlines()]
    result = []
    seen = set()
    for topic in chosen:
        if topic and topic.casefold() not in seen:
            result.append(topic)
            seen.add(topic.casefold())
    return result
