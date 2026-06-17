import streamlit as st
import anthropic
import json
import base64
import time

# ─── Page config ──────────────────────────────────────────────────
st.set_page_config(
    page_title="FactCheck AI — Automated Claim Verification",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── Styles ───────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
  html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

  .hero-title   { font-size: 2.6rem; font-weight: 700; color: #0F172A; line-height: 1.2; }
  .hero-sub     { font-size: 1.05rem; color: #475569; margin-top: 0.4rem; }
  .badge        { display: inline-block; padding: 3px 10px; border-radius: 20px; font-size: 0.75rem; font-weight: 600; }
  .badge-v      { background: #DCFCE7; color: #166534; }
  .badge-i      { background: #FEE2E2; color: #991B1B; }
  .badge-u      { background: #FEF3C7; color: #92400E; }
  .card         { background: #FFFFFF; border-radius: 12px; padding: 1.2rem 1.4rem; margin-bottom: 0.9rem;
                  border: 1px solid #E2E8F0; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }
  .card-v       { border-left: 4px solid #10B981; }
  .card-i       { border-left: 4px solid #EF4444; }
  .card-u       { border-left: 4px solid #F59E0B; }
  .claim-text   { font-size: 0.96rem; color: #1E293B; font-weight: 500; margin: 0.3rem 0 0.6rem 0; }
  .verdict-text { font-size: 0.88rem; color: #475569; }
  .real-fact    { font-size: 0.88rem; color: #1E3A5F; background: #EFF6FF; padding: 6px 10px;
                  border-radius: 6px; margin-top: 0.5rem; }
  .source-link  { font-size: 0.78rem; color: #64748B; margin-top: 0.4rem; }
  .stat-box     { background: #F8FAFC; border-radius: 10px; padding: 1rem; text-align: center;
                  border: 1px solid #E2E8F0; }
  .stat-num     { font-size: 2rem; font-weight: 700; }
  .stat-label   { font-size: 0.8rem; color: #64748B; margin-top: 2px; }
  .step-chip    { background: #0891B2; color: white; border-radius: 20px; padding: 3px 12px;
                  font-size: 0.8rem; font-weight: 600; display: inline-block; margin-bottom: 0.4rem; }
</style>
""", unsafe_allow_html=True)

# ─── Header ───────────────────────────────────────────────────────
col_h1, col_h2 = st.columns([5, 2])
with col_h1:
    st.markdown('<div class="hero-title">FactCheck AI 🔍</div>', unsafe_allow_html=True)
    st.markdown('<div class="hero-sub">Upload any PDF — the system extracts every factual claim and cross-references it against live web data.</div>', unsafe_allow_html=True)
with col_h2:
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.caption("Powered by Claude + Web Search")

st.markdown("---")

# ─── Core functions ───────────────────────────────────────────────
def get_client():
    api_key = st.secrets.get("ANTHROPIC_API_KEY", None)
    if not api_key:
        st.error("ANTHROPIC_API_KEY not found. Add it to your Streamlit secrets.")
        st.stop()
    return anthropic.Anthropic(api_key=api_key)


def extract_claims(client, pdf_base64: str) -> list:
    """Pass the PDF to Claude and extract all verifiable factual claims as JSON."""
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": pdf_base64,
                    },
                },
                {
                    "type": "text",
                    "text": (
                        "You are a precise fact-extractor. Read this document and identify every specific, "
                        "verifiable factual claim. Focus on: statistics, percentages, dates, financial figures, "
                        "technical specifications, named research findings, and any concrete numbers.\n\n"
                        "Return ONLY a valid JSON array — no preamble, no markdown fences. Format:\n"
                        "[\n"
                        '  {"id": 1, "claim": "exact claim text", "category": "statistic|date|financial|technical|other", '
                        '"context": "one sentence of surrounding context"}\n'
                        "]\n\n"
                        "Extract between 5 and 15 of the most important, specific claims. No vague statements."
                    ),
                },
            ],
        }]
    )
    raw = response.content[0].text.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(raw)


def verify_claims(client, claims: list) -> list:
    """Use Claude with web search to verify every extracted claim against live data."""
    claims_json = json.dumps(claims, indent=2)

    messages = [{
        "role": "user",
        "content": (
            "You are an expert fact-checker with access to live web search. "
            "Verify each claim below against current, authoritative sources.\n\n"
            f"Claims:\n{claims_json}\n\n"
            "For EVERY claim, search the web, then return a JSON array:\n"
            "[\n"
            '  {"id": 1, "claim": "original claim", "status": "Verified|Inaccurate|Unverifiable",\n'
            '   "verdict": "one sentence explanation", '
            '"real_fact": "correct current data if Inaccurate, or confirmation if Verified",\n'
            '   "source": "URL or source name"}\n'
            "]\n\n"
            "Status rules:\n"
            "- Verified: live data confirms the claim\n"
            "- Inaccurate: live data contradicts it (wrong number, outdated stat, false claim)\n"
            "- Unverifiable: cannot find reliable sources to confirm or deny\n\n"
            "Return ONLY the JSON array. Absolutely no other text."
        ),
    }]

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=messages,
    )

    # Walk content blocks in reverse to find the final text answer
    for block in reversed(response.content):
        if hasattr(block, "text"):
            raw = block.text.strip().replace("```json", "").replace("```", "").strip()
            if raw.startswith("["):
                return json.loads(raw)

    return []


# ─── UI ───────────────────────────────────────────────────────────
uploaded = st.file_uploader(
    "Upload a PDF document",
    type=["pdf"],
    help="Works best on documents containing statistics, reports, or data-heavy marketing content.",
)

if uploaded:
    col_m1, col_m2, col_m3 = st.columns(3)
    col_m1.metric("File", uploaded.name)
    col_m2.metric("Size", f"{uploaded.size / 1024:.1f} KB")
    col_m3.metric("Type", "PDF")

    if st.button("Run Fact Check →", type="primary", use_container_width=True):
        pdf_bytes  = uploaded.read()
        pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")
        client     = get_client()

        # ── Step 1: Extract claims ──
        step1 = st.container()
        with step1:
            st.markdown('<div class="step-chip">Step 1 / 2</div>', unsafe_allow_html=True)
            with st.spinner("Extracting verifiable claims from document..."):
                try:
                    claims = extract_claims(client, pdf_base64)
                except Exception as e:
                    st.error(f"Extraction failed: {e}")
                    st.stop()

        st.success(f"Found {len(claims)} verifiable claims. Searching the web to verify each one...")

        # ── Step 2: Verify claims ──
        step2 = st.container()
        with step2:
            st.markdown('<div class="step-chip">Step 2 / 2</div>', unsafe_allow_html=True)
            with st.spinner(f"Cross-referencing {len(claims)} claims against live web data... (30–90 seconds)"):
                try:
                    results = verify_claims(client, claims)
                except Exception as e:
                    st.error(f"Verification failed: {e}")
                    st.stop()

        if not results:
            st.warning("Verification returned no results. Try again or use a different document.")
            st.stop()

        # ── Summary ──
        st.markdown("## Results")
        verified_n     = sum(1 for r in results if r.get("status") == "Verified")
        inaccurate_n   = sum(1 for r in results if r.get("status") == "Inaccurate")
        unverifiable_n = sum(1 for r in results if r.get("status") == "Unverifiable")

        s1, s2, s3, s4 = st.columns(4)
        with s1:
            st.markdown(f"""
            <div class="stat-box">
              <div class="stat-num" style="color:#0F172A">{len(results)}</div>
              <div class="stat-label">Claims Checked</div>
            </div>""", unsafe_allow_html=True)
        with s2:
            st.markdown(f"""
            <div class="stat-box">
              <div class="stat-num" style="color:#10B981">{verified_n}</div>
              <div class="stat-label">Verified</div>
            </div>""", unsafe_allow_html=True)
        with s3:
            st.markdown(f"""
            <div class="stat-box">
              <div class="stat-num" style="color:#EF4444">{inaccurate_n}</div>
              <div class="stat-label">Inaccurate / Outdated</div>
            </div>""", unsafe_allow_html=True)
        with s4:
            st.markdown(f"""
            <div class="stat-box">
              <div class="stat-num" style="color:#F59E0B">{unverifiable_n}</div>
              <div class="stat-label">Unverifiable</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("---")

        # ── Per-claim cards ──
        status_order = {"Inaccurate": 0, "Unverifiable": 1, "Verified": 2}
        sorted_results = sorted(results, key=lambda r: status_order.get(r.get("status", "Unverifiable"), 1))

        for r in sorted_results:
            status  = r.get("status", "Unverifiable")
            badge   = {"Verified": "badge-v", "Inaccurate": "badge-i", "Unverifiable": "badge-u"}.get(status, "badge-u")
            card_cl = {"Verified": "card-v",  "Inaccurate": "card-i",  "Unverifiable": "card-u"}.get(status, "card-u")
            icon    = {"Verified": "✅",        "Inaccurate": "❌",       "Unverifiable": "⚠️"}.get(status, "⚠️")

            st.markdown(f"""
            <div class="card {card_cl}">
              <span class="badge {badge}">{icon} {status}</span>
              <div class="claim-text">"{r.get('claim', '')}"</div>
              <div class="verdict-text">{r.get('verdict', '')}</div>
              <div class="real-fact">📌 {r.get('real_fact', 'No correction available')}</div>
              <div class="source-link">🔗 Source: {r.get('source', 'N/A')}</div>
            </div>
            """, unsafe_allow_html=True)

        # ── Download JSON ──
        st.markdown("---")
        st.download_button(
            label="Download Full Report (JSON)",
            data=json.dumps(results, indent=2),
            file_name="factcheck_report.json",
            mime="application/json",
)
