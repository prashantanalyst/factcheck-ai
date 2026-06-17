import streamlit as st
from groq import Groq
import json
import fitz
import requests
import re
import time


# ─── Page Config ─────────────────────────────────────

st.set_page_config(
    page_title="FactCheck AI — Automated Claim Verification",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ─── Custom Styling ─────────────────────────────────

st.markdown("""
<style>

@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}


.hero-title {
    font-size: 2.6rem;
    font-weight: 700;
    color: #0F172A;
    line-height: 1.2;
}

.hero-sub {
    font-size: 1.05rem;
    color: #475569;
    margin-top: 0.4rem;
}


.badge {
    display:inline-block;
    padding:3px 10px;
    border-radius:20px;
    font-size:0.75rem;
    font-weight:600;
}


.badge-v {
    background:#DCFCE7;
    color:#166534;
}

.badge-i {
    background:#FEE2E2;
    color:#991B1B;
}

.badge-u {
    background:#FEF3C7;
    color:#92400E;
}


.card {
    background:white;
    border-radius:12px;
    padding:1.2rem 1.4rem;
    margin-bottom:0.9rem;
    border:1px solid #E2E8F0;
    box-shadow:0 1px 3px rgba(0,0,0,0.06);
}


.card-v {
    border-left:4px solid #10B981;
}

.card-i {
    border-left:4px solid #EF4444;
}

.card-u {
    border-left:4px solid #F59E0B;
}


.claim-text {
    font-size:0.96rem;
    color:#1E293B;
    font-weight:500;
    margin:0.3rem 0 0.6rem;
}


.verdict-text {
    font-size:0.88rem;
    color:#475569;
}


.real-fact {
    font-size:0.88rem;
    color:#1E3A5F;
    background:#EFF6FF;
    padding:6px 10px;
    border-radius:6px;
    margin-top:0.5rem;
}


.source-link {
    font-size:0.78rem;
    color:#64748B;
    margin-top:0.4rem;
}


.stat-box {
    background:#F8FAFC;
    border-radius:10px;
    padding:1rem;
    text-align:center;
    border:1px solid #E2E8F0;
}


.stat-num {
    font-size:2rem;
    font-weight:700;
}


.stat-label {
    font-size:0.8rem;
    color:#64748B;
}


.step-chip {
    background:#0891B2;
    color:white;
    border-radius:20px;
    padding:3px 12px;
    font-size:0.8rem;
    font-weight:600;
}

</style>
""", unsafe_allow_html=True)


# ─── Header ─────────────────────────────────────

col1, col2 = st.columns([5,2])

with col1:
    st.markdown(
        '<div class="hero-title">FactCheck AI 🔍</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="hero-sub">'
        'Upload any PDF and automatically verify claims using AI.'
        '</div>',
        unsafe_allow_html=True
    )


with col2:
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.caption("Powered by Groq Llama 3.3")


st.markdown("---")


# ─── Groq Client ─────────────────────────────────


def get_client():

    api_key = st.secrets.get("GROQ_API_KEY")

    if not api_key:
        st.error(
            "GROQ_API_KEY not found in Streamlit Secrets."
        )
        st.stop()

    return Groq(
        api_key=api_key
    )


# ─── PDF Text Extraction ─────────────────────────


def extract_pdf_text(pdf_bytes):

    try:

        document = fitz.open(
            stream=pdf_bytes,
            filetype="pdf"
        )

        text = ""

        for page in document:
            text += page.get_text()

        document.close()


        if len(text.strip()) < 50:
            raise Exception(
                "PDF does not contain enough readable text."
            )

        return text[:30000]


    except Exception as e:

        raise Exception(
            f"Could not read PDF: {str(e)}"
)

# ─── JSON Cleanup Helper ─────────────────────────


def clean_json(text):

    text = text.strip()

    text = text.replace("```json", "")
    text = text.replace("```", "")

    start = text.find("[")

    end = text.rfind("]")

    if start != -1 and end != -1:
        return text[start:end + 1]

    raise Exception(
        "AI did not return valid JSON."
    )


# ─── Claim Extraction with Groq ─────────────────


def extract_claims(client, pdf_text):

    prompt = f"""
You are a professional fact extraction system.

Analyze the following document and identify the most important factual claims that can be verified.

Extract:
- Statistics
- Percentages
- Dates
- Financial numbers
- Technical specifications
- Research findings
- Numerical statements

Rules:
- Ignore opinions and marketing language.
- Extract between 5 and 15 claims.
- Keep the exact claim wording whenever possible.
- Return only valid JSON.
- Do not add markdown.

Required format:

[
  {{
    "id": 1,
    "claim": "exact claim",
    "category": "statistic/date/financial/technical/other",
    "context": "short surrounding context"
  }}
]

Document:

{pdf_text}

"""

    try:

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            temperature=0.1,
            max_tokens=2000,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You extract factual claims and always respond "
                        "with clean JSON only."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )


        raw_output = (
            response
            .choices[0]
            .message
            .content
        )


        cleaned_output = clean_json(
            raw_output
        )


        claims = json.loads(
            cleaned_output
        )


        if not isinstance(claims, list):
            raise Exception(
                "Output is not a JSON list."
            )


        if len(claims) == 0:
            raise Exception(
                "No claims found."
            )


        return claims


    except json.JSONDecodeError:

        raise Exception(
            "Groq returned invalid JSON. Please try another document."
        )


    except Exception as e:

        raise Exception(
            f"Claim extraction failed: {str(e)}"
    )

    # ─── Web Evidence Search ─────────────────────────


def search_web(query):

    try:

        url = "https://duckduckgo.com/html/"

        response = requests.get(
            url,
            params={
                "q": query
            },
            headers={
                "User-Agent":
                "Mozilla/5.0"
            },
            timeout=10
        )


        text = response.text


        # Keep only a limited amount of text
        evidence = re.sub(
            r"<.*?>",
            " ",
            text
        )

        evidence = re.sub(
            r"\s+",
            " ",
            evidence
        )


        return evidence[:5000]


    except Exception:

        return "No web evidence available."


# ─── Verify Claims with Groq ─────────────────────


def verify_claims(client, claims):

    results = []


    for item in claims:

        claim = item.get(
            "claim",
            ""
        )


        web_data = search_web(
            claim
        )


        prompt = f"""
You are an expert fact checker.

Your job is to compare a claim with live web evidence.

Claim:

{claim}


Web Evidence:

{web_data}


Decide one status only:

Verified:
The evidence confirms the claim.

Inaccurate:
The evidence shows the claim is wrong,
outdated, or misleading.

Unverifiable:
There is not enough reliable evidence.


Return ONLY this JSON:

{{
"id": {item.get("id", 0)},
"claim": "{claim}",
"status": "Verified or Inaccurate or Unverifiable",
"verdict": "Short explanation",
"real_fact": "Correct fact or confirmation",
"source": "Name of website or web source"
}}

Do not return markdown.
"""


        try:

            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                temperature=0.1,
                max_tokens=500,
                messages=[
                    {
                        "role":
                        "system",
                        "content":
                        "You are a precise fact checking AI. "
                        "Always return valid JSON only."
                    },
                    {
                        "role":
                        "user",
                        "content":
                        prompt
                    }
                ]
            )


            raw = (
                response
                .choices[0]
                .message
                .content
            )


            raw = raw.replace(
                "```json",
                ""
            ).replace(
                "```",
                ""
            ).strip()


            result = json.loads(
                raw
            )


            results.append(
                result
            )


            time.sleep(1)


        except Exception:

            results.append(
                {
                    "id":
                    item.get("id", 0),
                    "claim":
                    claim,
                    "status":
                    "Unverifiable",
                    "verdict":
                    "The system could not verify this claim.",
                    "real_fact":
                    "No reliable evidence found.",
                    "source":
                    "Unavailable"
                }
            )


    return results

# ─── Main UI ───────────────────────────────────

uploaded = st.file_uploader(
    "Upload a PDF document",
    type=["pdf"],
    help="Works best with reports, research papers, and documents containing statistics."
)


if uploaded:

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "File",
        uploaded.name
    )

    col2.metric(
        "Size",
        f"{uploaded.size / 1024:.1f} KB"
    )

    col3.metric(
        "Type",
        "PDF"
    )


    if st.button(
        "Run Fact Check →",
        type="primary",
        use_container_width=True
    ):

        client = get_client()

        pdf_bytes = uploaded.read()


        # Step 1
        st.markdown(
            '<div class="step-chip">Step 1 / 2</div>',
            unsafe_allow_html=True
        )

        with st.spinner(
            "Extracting claims from PDF..."
        ):

            try:
                pdf_text = extract_pdf_text(
                    pdf_bytes
                )

                claims = extract_claims(
                    client,
                    pdf_text
                )

            except Exception as e:

                st.error(
                    f"Extraction failed: {e}"
                )

                st.stop()


        st.success(
            f"Found {len(claims)} verifiable claims."
        )


        # Step 2
        st.markdown(
            '<div class="step-chip">Step 2 / 2</div>',
            unsafe_allow_html=True
        )


        with st.spinner(
            "Searching the web and verifying claims..."
        ):

            try:

                results = verify_claims(
                    client,
                    claims
                )

            except Exception as e:

                st.error(
                    f"Verification failed: {e}"
                )

                st.stop()


        if not results:

            st.warning(
                "No verification results found."
            )

            st.stop()


        # Summary
        st.markdown(
            "## Results"
        )


        verified = sum(
            1 for x in results
            if x.get("status") == "Verified"
        )

        inaccurate = sum(
            1 for x in results
            if x.get("status") == "Inaccurate"
        )

        unverifiable = sum(
            1 for x in results
            if x.get("status") == "Unverifiable"
        )


        cols = st.columns(4)


        data = [
            (len(results), "Claims Checked"),
            (verified, "Verified"),
            (inaccurate, "Inaccurate"),
            (unverifiable, "Unverifiable")
        ]


        for col, item in zip(cols, data):

            with col:

                st.markdown(
                    f"""
                    <div class="stat-box">
                        <div class="stat-num">
                            {item[0]}
                        </div>

                        <div class="stat-label">
                            {item[1]}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )


        st.markdown("---")


        order = {
            "Inaccurate": 0,
            "Unverifiable": 1,
            "Verified": 2
        }


        results = sorted(
            results,
            key=lambda x:
            order.get(
                x.get("status"),
                1
            )
        )


        for r in results:


            status = r.get(
                "status",
                "Unverifiable"
            )


            badge = {
                "Verified": "badge-v",
                "Inaccurate": "badge-i",
                "Unverifiable": "badge-u"
            }.get(
                status,
                "badge-u"
            )


            card = {
                "Verified": "card-v",
                "Inaccurate": "card-i",
                "Unverifiable": "card-u"
            }.get(
                status,
                "card-u"
            )


            icon = {
                "Verified": "✅",
                "Inaccurate": "❌",
                "Unverifiable": "⚠️"
            }.get(
                status,
                "⚠️"
            )


            st.markdown(
                f"""
                <div class="card {card}">
                    <span class="badge {badge}">
                        {icon} {status}
                    </span>

                    <div class="claim-text">
                        "{r.get('claim', '')}"
                    </div>

                    <div class="verdict-text">
                        {r.get('verdict', '')}
                    </div>

                    <div class="real-fact">
                        📌 {r.get('real_fact', '')}
                    </div>

                    <div class="source-link">
                        🔗 Source: {r.get('source', 'Unknown')}
                    </div>

                </div>
                """,
                unsafe_allow_html=True
            )


        st.markdown("---")


        st.download_button(
            label="Download Full Report (JSON)",
            data=json.dumps(
                results,
                indent=2
            ),
            file_name="factcheck_report.json",
            mime="application/json"
        )
        
