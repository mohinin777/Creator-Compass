# Creator Compass

A lightweight Streamlit prototype for exploring a creator's interests and choosing
YouTube content topics before research. See [PROJECT_BRIEF.md](PROJECT_BRIEF.md)
for the intended full workflow.

## Current version

- Editable questionnaire: interests, skills, expertise, preferred styles, weekly
  production time, budget, on-camera preference, and constraints.
- Optional resume/LinkedIn **text** as a reference. There is no scraping, LinkedIn
  login, or automatic text extraction yet. Enter reviewed strengths in the
  questionnaire; text is not sent to an LLM or saved to disk by the app.
- Local, deterministic topic suggestions with their profile-based rationale.
  These are starter prompts, not claims of market demand or LLM output.
- Required topic selection: check suggested rows, edit their text, add custom
  topics, then confirm. Only confirmed topics appear in subsequent screens.
  Updating the saved profile resets topic confirmation.
- Bounded real-data loader and an on-demand sample/field viewer with explicit
  loading, empty, and failure states. No demonstration records are substituted.
- Creator discovery over the real video metadata: ranked title matches for each
  confirmed topic, grouping by channel handle, source links derived from valid
  video IDs, and recorded metrics with collection timestamps.
- Real comment sampling for selected matching videos, manual review, and an
  optional structured LLM classifier with source-quote validation and request
  category counts across distinct videos.
- Evidence-gated channel hypotheses, profile/production assessments, optional
  manual trend observations, adjustable weights, a transparent partial score,
  ranking, and downloadable source evidence. No paid API is required for the
  manual-review path.

## Launch

Use Python 3.12 (the version tested here):

```bash
cd /path/to/Creator-Compass
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py --server.headless=true --browser.gatherUsageStats=false
```

In the prepared cloud environment, use the existing environment instead:

```bash
cd /workspace/Creator-Compass
source /workspace/.creator-compass-setup/activate.sh
python -m streamlit run app.py --server.headless=true --server.address=127.0.0.1 --server.port=8501 --browser.gatherUsageStats=false
```

The cloud activation sets writable caches under `/workspace/.cache`. If using a
fresh environment with a read-only home, set `XDG_CACHE_HOME` and `HF_HOME` to a
writable directory before loading data. No API key is required for the profile,
topic suggestions, manual comment review, or this public dataset. Automated
comment classification requires an LLM API credential. Profiles are held in the current
Streamlit session, not a persistent profile store.

## Selected dataset and development sample

Only [`brianhliou/youtube-comment-exposure`](https://huggingface.co/datasets/brianhliou/youtube-comment-exposure)
is used. The dataset has no default configuration: the actual Hugging Face loading
error requires choosing `videos` or `comments`. The loader uses:

```python
from datasets import load_dataset

dataset = load_dataset(
    "brianhliou/youtube-comment-exposure", "videos", streaming=True
)
# Discover split names instead of assuming them, then take a bounded prefix.
```

In the app, open **Dataset sample**, choose a configuration, and click
**Load / retry dataset sample**. Or use the reusable CLI:

```bash
python -m creator_compass.sample --configuration videos --limit 10
python -m creator_compass.sample --configuration comments --limit 20
```

The first available split is used unless the CLI caller specifies `--split`.
The `videos` configuration exposed `train` during the live loading attempt.
Samples are limited to 1–200 materialized records, cached in application memory
for one hour, and are not committed or exported. Streaming compressed JSON may
transfer more bytes than the selected records and does not create a random sample.
The first records are collection-order biased, not representative research.

**Live validation:** network access works after the environment network update.
Five actual records from each configuration were loaded through `datasets`.
The full `videos` split was also loaded: **633 records**, with split exhaustion
verified. Both configurations expose `train`.

Observed fields relevant to the application:

| Configuration | Observed fields relevant to the app |
| --- | --- |
| videos | `video_id`, `channel_handle`, `title`, `category_id`, `published_at`, `duration_seconds`, `is_short`, `view_count`, `like_count`, `comment_count`, `collected_comments` |
| comments | `comment_id`, `video_id`, `text`, `like_count`, `reply_count`, `published_at`, `author_hash` |

Video/comment joins should use `video_id`. `author_hash` identifies a comment
writer, not the video's creator. `channel_handle` is the declared video-side
creator field. The runtime field viewer reports only columns that actually occur
in loaded records; missing/unrecognized fields remain unavailable. Discovery links are constructed only from observed video IDs matching YouTube’s
11-character ID format; missing or invalid IDs produce no link.

The card declares CC BY 4.0 for the collection/schema/derived fields and explains
that comment text belongs to its authors and YouTube API terms also apply. Read
its licensing section before caching or redistribution. The static dataset
covers a limited set of creators/videos, not current or comprehensive YouTube.
Comments are self-selected; missing topics do not establish absent competition.
Google Trends data is unavailable in this version, and no trend values, audience
gaps, opportunity scores, or success predictions are produced.

## Validation

```bash
python -m unittest discover -s tests -v
python -m pip check
```

Tests cover bounded loading with explicitly mocked test fixtures, failure
propagation, missing fields, topic selection/editing and deduplication, profile
saving/reset, required confirmation, and UI network-error handling. Discovery
tests cover ranking, explanations, deduplication, missing identifiers, bounded
catalog coverage, and exclusion of unconfirmed topics from results. Comment tests
cover scan limits, sparse/empty samples, duplicate filtering, revision-keyed cache
reuse, datetime serialization, evidence validation, distinct-video counts, manual
review, changed-settings invalidation, and mocked structured LLM responses. Unit fixtures
are never used as application data. Streamlit AppTest executes the UI, while
local HTTP checks verify the running server; neither proves remote dataset access.

## Creator discovery

After confirming topics, open **3 · Creator discovery** and click **Load video
catalog and discover creators**. The small video metadata table is loaded once
and cached in application memory for one hour. A 5,000-row safety cap detects and
reports truncation if the dataset grows; it does not silently claim full coverage.
Only the selected split is searched. Profiles and topic text are matched locally.

Matching uses case-insensitive word overlap in actual titles, removing common
words and generic suggestion-template wording. Each query word has weight
`1 + log((number_of_usable_titles + 1) / (titles_containing_word + 1))`.
Title relevance is the sum of matched query-word weights divided by the total
query-word weight. Duplicate video IDs are collapsed. Nonmatching titles are
excluded. No fuzzy/semantic matching, synonym expansion, or category-label
inference is performed; a zero-match topic may still occur in the dataset under
different wording. Partial matches need human review. A title-relevance value
is neither an opportunity score nor evidence of audience demand.

Each topic shows matching-video and identified-channel counts, grouping only by
observed `channel_handle` (case-insensitively). Missing handles are excluded from
channel counts and reported. Up to 20 ranked videos are displayed with matched
words, query words, recorded engagement counts and statistics timestamps.
Blank metrics mean unavailable, not zero. Counts describe only matched dataset
records, not competitive intensity across YouTube. Live checks found two title
matches each for `cooking` and `gaming`, and zero for `Python` and `science`;
these are lexical results, not a topic-coverage audit.

## Comment sampling and analysis

Open **4 · Comment analysis** after discovery. Choose a confirmed topic and up to
30 of its matching videos (first 10 selected initially), then sample 20–50 comments
per video. The default scan examines at most 100,000 source rows; choose a smaller
or larger bound explicitly, up to 1,500,000. It stops early when every target is
filled. The compressed stream is read sequentially, so later videos may have no
comments within a bounded scan. Network transfer may exceed materialized rows.

The sampler retains the first usable comments per video, filters duplicate IDs,
and reports scanned rows, stop reason, and per-video sample counts. This is a
biased prefix sample, not random or representative. A zero count means no usable
comments were found within that scan, not an absence of audience needs. Original
text, IDs, timestamps, and recorded engagement fields remain visible with source
links constructed from observed video/comment IDs. No author hashes are retained
in this cache.

Only bounded evidence samples are saved to ignored `.cache/comment_samples/`
JSON files for reuse. Keys include the actual dataset commit, selected video IDs,
per-video limit, scan limit, and cache schema version. Dataset content is pinned
to that commit while sampling. This avoids rescanning for identical parameters,
but a larger scan or different selection can require another scan. The full
comment corpus is not written to a local index. Delete these local cache files
to remove stored samples; respect the dataset's reuse conditions. Profiles,
resume text, and review/classification state are not written to this cache.

Select up to 100 retained comments for classification/review. **Manual review**
works without credentials: choose a category for every row and paste an exact
supporting quote for request categories. Unreviewed comments are not silently
counted as feedback. Human-reviewed and model-produced results are labeled.

### Optional LLM classification

The default is OpenAI **gpt-4.1-nano**, selected as a low-cost model for this narrow
classification task. Configure the credential securely; never enter it in chat
or commit it to a file:

- `LLM_API_KEY2`: provider API credential; required for the LLM button.
- `LLM_MODEL`: defaults to `gpt-4.1-nano`.

In cloud environment settings, a requirement for `LLM_API_KEY2`, the model
suggestion, and the `api.openai.com` destination have been saved as a draft.
Enter the key securely, review/save the configuration, and publish/apply it as
required by the environment UI. A draft save does not supply credentials or
prove a live model call works. A later live test reached the provider but was
rejected with HTTP 429, `insufficient_quota` / `credit_balance_exhausted`.
**Successful live LLM classification remains unverified.** Resolve API billing
before retrying; the complete manual-review path works without credits. Mocked
tests cover request/response handling and evidence validation.

Classification runs only on an explicit button click and may incur API charges.
Each request sends at most 25 comment IDs/texts, capped at 4,000 characters per
comment, and uses a strict JSON schema. The profile/resume is never included.
Requests go only to the fixed `https://api.openai.com/v1/chat/completions`
endpoint; configurable destinations have been removed and redirects are blocked
to prevent forwarding credentials. Model overrides must support strict JSON-schema
outputs. HTTPS verification remains enabled. There are no automatic
retries after model errors, and partial results are not accepted; earlier
successful requests in a failed multi-batch operation may still incur charges.

The seven categories come from the brief. The validator rejects unknown or
duplicate IDs, missing rows, unsupported labels, and invented quotes. Excerpts
must match source text exactly; request categories need nonempty evidence.
This validates references, not the model's interpretation: review its categories
and original comments. Summaries count comments and distinct videos by category
and retain up to five source excerpts per category. Recurrence across videos can
suggest an angle to investigate; it does not establish a shared specific unmet
need or prove missing video coverage. No automated coverage comparison has been
implemented yet. Results are scoped to the confirmed topic, selected videos,
sample settings and classification subset; changed settings require a new sample
or classification before summaries appear.

Live checks retained 20 actual comments for the first observed video and verified
the `video_id` join and an identical cache reload. This validates the sampling
path, not coverage across all matched videos or model classification quality.

## Channel ideas and scorecard

Use **5 · Recommendations** after saving reviewed categories in step 4:

1. Describe one specific shared viewer need and the intended audience.
2. Select supporting request-comment IDs from at least **two distinct videos**.
3. Inspect linked source videos/titles and record what coverage you observed and
   what remains uncertain. A title or a request alone cannot establish a gap.
4. Save up to three distinct supported hypotheses. Do not manufacture extra
   ideas when evidence supports fewer than two. One supported idea stays one;
   insufficient evidence produces a clear message rather than fabricated ideas.
5. For each concept, assess creator fit and explain it against your saved profile,
   estimate weekly production effort, and optionally enter actual trend data with
   source, search term, region and observation period.
6. Adjust the five weights and inspect the ranking. Download the JSON report to
   retain hypotheses, source excerpts, dataset revision, inputs and calculations.

Concepts are local templates built from your specific need, topic, target
audience and preferred formats. Specific-need grouping, coverage review, fit and
production estimates are **human judgments**, not automated gap findings. Model
classifications, if used, still need review. Data and scores do not predict success.

All dimensions use a 0–5 scale:

| Dimension | Calculation / source |
| --- | --- |
| Creator fit | Your 0–5 rating, included only after you explain its relationship to your stated strengths |
| Search interest | Your actual 0–100 relative observation / 20, included only with source/scope; otherwise unknown |
| Sampled competition | `5 / (1 + matching identified dataset channels)`; lexical matching and dataset coverage limit this heuristic |
| Audience evidence | `min(5, distinct supporting videos)`; recurrence is not proof of unmet demand |
| Production feasibility | `min(5, 5 × available weekly hours / estimated weekly production hours)`; budget/style constraints remain a separate judgment |

The weighted score is `sum(available value × weight) / sum(available weights)`.
Unknown dimensions and zero weights are excluded; an all-zero denominator yields
unknown, not zero. Scores are marked partial when any dimension is unknown. Missing
trend evidence never becomes a fabricated trend score. Changing weights updates
scores and ranking immediately. The component table shows the source/formula.

Saved hypotheses are tied to the exact topic/sample/classification snapshot.
Changing the active sampling settings, review subset, or saved categories hides
stale recommendations until the current evidence is reviewed. Final reports
include comment text and source references but no API keys or resume text. Reports
are downloaded only on request; review state otherwise remains in session memory.

## Running the manual-review MVP

No API purchase is needed to exercise the workflow:

1. Launch `python -m streamlit run app.py` as described above.
2. Save a creator profile; optional resume text is a reference to review yourself.
3. Select/edit/add topics and **confirm** them.
4. Load the catalog and inspect creator/video matches.
5. Sample comments and review 5–10 at a time using the manual category table.
6. Group a specific need only when source requests support it across two videos.
7. Compare supported channel ideas with the scorecard and download the report.

Sparse topics and samples may correctly stop at insufficient evidence. Increase
the scan bound or select other genuinely relevant videos; do not convert absence
of sampled evidence into a market claim. Live sampling validated 20 comments each
from two observed AI-title matches after scanning 6,101 source rows. A separate
pair had no comments within the first 100,000 scanned rows, and the app correctly
reported zero sampled coverage. Tests use explicitly synthetic fixtures to exercise
recommendations; they are never presented as actual research findings.

## Remaining automation limits

The manual-review MVP supports the full navigation path, while optional LLM
classification is blocked by the provider project's exhausted credits. Resume
extraction, LLM topic suggestions, automatic semantic need grouping, and automatic
video-content coverage comparison remain future work. The current deterministic
suggestions and human-reviewed hypotheses are labeled accordingly. There is no
hosted deployment, login or durable profile store. Launch from the workspace or a
local checkout; this version is being shared on a GitHub review branch.
