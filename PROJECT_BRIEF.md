# Creator Compass — Project Brief

## Goal
Build a lightweight, portfolio-ready web dashboard for aspiring YouTube creators. Given a creator's interests, strengths, and experience, suggest content topics, let the user choose which topics to investigate, find relevant creators/videos in a fixed YouTube dataset, identify potential viewer needs from comments, and recommend 2–3 channel ideas with a transparent, adjustable opportunity scorecard.

This is a **quick Codex experimentation project**, not a production research platform. Prioritize a working end-to-end app, simplicity, and evidence-backed outputs. Do not overengineer.

## Selected dataset — do not run a separate dataset-selection or audit phase
Use the Hugging Face dataset **`brianhliou/youtube-comment-exposure`**:
https://huggingface.co/datasets/brianhliou/youtube-comment-exposure

Load it in Python with the Hugging Face `datasets` package:

```python
from datasets import load_dataset

dataset = load_dataset("brianhliou/youtube-comment-exposure")
```

If the repository requires an explicit split, configuration, or other supported loading syntax, consult its dataset card and adjust the call. Do not assume a particular split name or column schema. Load a small development subset first, then build a repeatable local preprocessing process for the full dataset. Prefer a local Parquet cache or DuckDB index if needed; do not load or send all comments to an LLM.

**Network access:** the first download requires the Codex environment to reach Hugging Face (at least `huggingface.co`, and potentially `datasets-server.huggingface.co` and dataset file-hosting endpoints). The `datasets` library does not bypass network restrictions. If network access fails, report the exact blocker; do not silently substitute fabricated data. Respect the dataset's actual license and reuse conditions.

No separate dataset audit, alternative dataset search, or formal go/no-go checkpoint is required. During implementation, perform only necessary schema checks (e.g., inspect column names, available splits, IDs, title and channel fields) so the code works. If a required field is absent, degrade gracefully and explain the limitation rather than inventing it.

## Core user flow

### 1. Creator profile
Allow either:
- Guided selection of interests, skills, personal/professional expertise, preferred content style, and production constraints; or
- User-supplied resume/LinkedIn profile **text** for LLM extraction of strengths and content interests.

Allow review and edits. Do not scrape LinkedIn or require LinkedIn login. A LinkedIn URL may be displayed as a reference, but it is not a source of automatically scraped content.

### 2. Topic suggestions
Generate a range of potential YouTube content topics based on creator fit. Where actual Google Trends observations are available, use them as relative search-interest signals. Do not invent Google Trends scores or assume public access to a Trends API. For the MVP, allow manually supplied trend data; if unavailable, show “trend data unavailable” and proceed using the other evidence.

### 3. Topic selection — required
Present suggested topics as selectable cards. Let the user select, edit, and add topics. Only chosen topics proceed to creator and audience research.

### 4. Creator discovery and potential audience gaps
Search the downloaded dataset for videos relevant to each selected topic, using the available title/category/metadata fields and lightweight relevance ranking. Group results by creator/channel when reliable identifiers are available. Show real titles, creator identifiers, source links, and metrics **only when present**.

For a relevant sample of videos, sample approximately 20–50 comments per video initially, with an approximate target of 10–30 videos when the data supports it. Use an LLM with structured outputs to categorize comments into:
- Tutorial requests
- Requests for practical examples
- Confusion or unanswered questions
- Comparison requests
- Requests for deeper coverage
- Audience-specific requests
- General feedback / other

Aggregate repeated needs across videos, retaining representative source comments and counts of distinct videos. Compare viewer requests with observed topic coverage to suggest **possible** differentiation angles. These are hypotheses based on a limited static dataset, not proven gaps across all of YouTube. If a topic has insufficient dataset coverage, say so and do not manufacture evidence.

### 5. Channel recommendations and opportunity scorecard
Generate 2–3 distinct channel ideas **where evidence supports them**. For each show:
- Channel concept and target audience
- Why it fits the creator
- Search-interest evidence, if available
- Relevant creators and videos
- Potential differentiation with supporting viewer comments
- An adjustable opportunity scorecard

Scorecard dimensions:
1. Creator fit
2. Search-interest signal (when available)
3. Competitive intensity (within the sampled dataset only)
4. Strength of audience-gap evidence
5. Production feasibility

Show each component's evidence and calculation. Allow users to change weights and see rankings update. Missing information is **unknown**, not zero; exclude unavailable dimensions from weighted scoring or clearly mark a partial score. The score is a heuristic decision aid, not a prediction of channel success.

## Technology and architecture
Prefer:
- Streamlit for a simple multi-step web UI
- Python for app and analysis logic
- Hugging Face `datasets` to load the selected dataset
- Pandas/Polars and Parquet, with DuckDB only if needed
- An LLM API for topic generation, comment categorization, and recommendation explanations
- Environment variables for API credentials

Separate data ingestion, topic matching, LLM classification, score calculation, and UI. Cache reusable work where permitted. Do not pass a million comments to an LLM or reprocess the whole dataset for every user query. Add reasonable loading, empty-state, and error handling. Never expose API keys.

## Scope limits
**Do not build:** live YouTube Data API retrieval, YouTube website scraping, LinkedIn scraping, user accounts, video production tools, thumbnails, scripts, content calendars, channel performance tracking, vector databases, custom model training, or production-scale infrastructure.

## Limitations to document
- The fixed dataset covers only its included videos, creators, and topics; it is not comprehensive or current YouTube coverage.
- Large comment count does not guarantee broad topic coverage.
- Viewer comments are self-selected and not representative of all viewers.
- A topic absent from the sampled videos is not necessarily absent from YouTube.
- Trend data may be unavailable; Google Trends is relative search interest, not forecast YouTube viewership.
- Scores are transparent heuristics, not success predictions.
- The actual dataset schema, reuse permissions, and access requirements govern implementation.

## Success criteria
- Creator can enter/edit a profile.
- App suggests topics, and creator can explicitly select/edit/add topics before research.
- App finds relevant real videos/creators from the selected local dataset when available.
- App categorizes sampled comments and links possible audience needs to evidence.
- App proposes 2–3 channel ideas when evidence permits, with adjustable scoring.
- App handles unsupported topics, missing data, and unavailable trends honestly.
- Full workflow runs locally with clear setup instructions, tests, and README.

## Build sequence (no standalone dataset audit)
1. Scaffold Streamlit app and dataset loader using `datasets.load_dataset`; load a small development subset and inspect only fields needed for implementation.
2. Implement creator profile, topic suggestions, and **user topic selection**.
3. Implement local topic matching and creator/video discovery.
4. Implement sampled comment classification and evidence-backed gap hypotheses.
5. Implement channel recommendations and adjustable opportunity scorecard.
6. Test several different profiles/topics, polish UI, and document the dataset and limitations.

At each stage run the relevant code/tests, report what actually works, and do not invent data or functionality.
