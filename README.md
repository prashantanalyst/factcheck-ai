# FactCheck AI

A deployed fact-checking web application that reads a PDF, extracts every verifiable claim, searches the live web to verify each one, and flags them as **Verified**, **Inaccurate**, or **Unverifiable**.

Built for the CogCulture Product Management Trainee Assessment — Part 2.

---

## What It Does

1. **Extract** — Reads any PDF and identifies specific claims: statistics, dates, financial figures, technical specs, research findings
2. **Verify** — Searches the live web using Claude's built-in web search to cross-reference each claim against current authoritative data
3. **Report** — Returns a color-coded card for every claim with the original text, verdict, corrected fact (if wrong), and source

The system is specifically designed to catch "trap documents" containing intentional falsehoods or outdated statistics. Inaccurate claims are shown first so problems surface immediately.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Streamlit |
| AI model | Groq |
| Web search | Groq tool (native) |
| PDF handling | Base64 document API (no external library needed) |
| Deployment | Streamlit Cloud |

---

## Setup & Deployment

### 1. Clone the repository

```bash
git clone https://github.com/prashantanalyst/factcheck-ai.git
cd factcheck-ai
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Add your Groq API

For local development, create `.streamlit/secrets.toml`:

```toml
GROQ_API_KEY = "gsk_abc123xyz..."
```

For Streamlit Cloud deployment, add the key in **Settings → Secrets**.

### 4. Run locally

```bash
streamlit run app.py
```

### 5. Deploy to Streamlit Cloud

1. Push this repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your repo
4. Set `GROQ_API_KEY` in the Secrets section
5. Deploy — your app will be live at `https://YOUR_APP.streamlit.app`

---

## How the Verification Works

**Claim Extraction (Groq + PDF):**
Claude reads the full PDF as a base64-encoded document and returns a structured JSON list of verifiable claims. It prioritizes concrete, checkable facts over vague statements.

**Verification (Groq + Web Search):**
For each claim, gorq uses the `web_search_20250305` tool to search for current, authoritative data, then compares the claim to what it finds. The model applies these rules:
- **Verified** — current web data confirms the claim is accurate
- **Inaccurate** — current web data contradicts the claim (wrong number, outdated stat, false assertion)
- **Unverifiable** — no reliable sources found to confirm or deny

Results are sorted with Inaccurate claims first so problems surface at the top.

---

## Project Structure

```
factcheck-ai/
├── app.py              # Main Streamlit application
├── requirements.txt    # Python dependencies
└── README.md           # This file
```

---

## Notes

- Works best on documents under 10MB
- Verification typically takes 30–90 seconds depending on the number of claims
- The app downloads a full JSON report of all results
- API credits are required — add your Anthropic API key before deploying
-
