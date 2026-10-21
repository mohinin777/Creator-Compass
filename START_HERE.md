# Start here — Creator Compass MVP

This ZIP contains the app source and tests. It does not include credentials,
dataset records, or the Python environment. This is the manual-review MVP review branch.

## 1. Install Python
Install Python 3.12 from https://www.python.org/downloads/ if needed.
On Windows, enable “Add Python to PATH” during installation.

## 2. Extract this ZIP
Extract it to a normal folder first. Open a terminal in the Creator-Compass
folder containing app.py and requirements.txt.

## 3. Set up and launch
Windows (Command Prompt):

    python -m venv .venv
    .venv\Scripts\python.exe -m pip install -r requirements.txt
    .venv\Scripts\python.exe -m streamlit run app.py --browser.gatherUsageStats=false

macOS / Linux:

    python3.12 -m venv .venv
    .venv/bin/python -m pip install -r requirements.txt
    .venv/bin/python -m streamlit run app.py --browser.gatherUsageStats=false

Open the Local URL printed by Streamlit in your browser. Keep the terminal
open while using the app. Press Ctrl+C in the terminal to stop it.
Later launches only need the last command. If macOS/Linux cannot find
python3.12, check that Python 3.12 is installed and use its executable path.

Internet is needed to install packages and to load real Hugging Face data.
If you use a restricted network, see README.md for dataset host details.

## 4. Review the app without API charges
1. Save a creator profile. Resume text is optional and manually reviewed.
2. Select/edit/add topics and confirm them.
3. In Creator discovery, load the real video catalog and inspect matches.
4. In Comment analysis, select matching videos and sample comments. The first
   request scans the full comments split and creates a reusable local index;
   allow a few minutes and enough free disk space. Review
   5–10 comments at first using Manual categorization / review. Choose a
   category for every displayed row and paste exact quotes for requests.
5. In Recommendations, group one specific need only if reviewed requests
   support it across two distinct videos. Record the intended audience and
   observed video coverage. Compare supported ideas with adjustable weights.

Some topics have no matches or insufficient sampled evidence. This is an
expected honest result; the app does not invent research data or extra ideas.
Manual review requires no API key. Automated classification is optional and
requires your own paid OpenAI API access through LLM_API_KEY2. Do not put
credentials in source files or share them in chat. No credentials are bundled.

Hypotheses and review state live in your browser session. Use the JSON download
in Recommendations to keep your evidence/scorecard. The full comment index and bounded samples
are cached locally in .cache/comment_samples; delete that directory to remove
them. Indexing and manual review do not consume paid LLM tokens. Scores are transparent heuristics, not predictions of channel success.

See README.md for formulas, limitations, and test instructions.
