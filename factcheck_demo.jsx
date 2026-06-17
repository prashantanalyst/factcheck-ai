import { useState, useRef } from "react";

const STATUS_CONFIG = {
  Verified:      { bg: "#DCFCE7", border: "#10B981", badge: "#166534", badgeBg: "#DCFCE7", icon: "✅", label: "Verified" },
  Inaccurate:    { bg: "#FEF2F2", border: "#EF4444", badge: "#991B1B", badgeBg: "#FEE2E2", icon: "❌", label: "Inaccurate / Outdated" },
  Unverifiable:  { bg: "#FFFBEB", border: "#F59E0B", badge: "#92400E", badgeBg: "#FEF3C7", icon: "⚠️", label: "Unverifiable" },
};

function ClaimCard({ result, index }) {
  const cfg = STATUS_CONFIG[result.status] || STATUS_CONFIG.Unverifiable;
  return (
    <div style={{
      background: "#fff",
      border: `1px solid #E2E8F0`,
      borderLeft: `4px solid ${cfg.border}`,
      borderRadius: "10px",
      padding: "1rem 1.2rem",
      marginBottom: "0.75rem",
      boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
      animation: `fadeIn 0.3s ease ${index * 0.05}s both`,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px" }}>
        <span style={{
          background: cfg.badgeBg, color: cfg.badge,
          borderRadius: "20px", padding: "2px 10px",
          fontSize: "0.75rem", fontWeight: 700,
        }}>
          {cfg.icon} {cfg.label}
        </span>
        <span style={{ fontSize: "0.72rem", color: "#94A3B8" }}>#{result.id}</span>
      </div>
      <p style={{ margin: "6px 0", fontSize: "0.94rem", color: "#1E293B", fontWeight: 500, lineHeight: 1.4 }}>
        "{result.claim}"
      </p>
      <p style={{ margin: "4px 0 8px", fontSize: "0.86rem", color: "#475569", lineHeight: 1.45 }}>
        {result.verdict}
      </p>
      <div style={{
        background: "#EFF6FF", borderRadius: "6px",
        padding: "7px 11px", fontSize: "0.84rem", color: "#1E3A5F", marginBottom: "6px",
      }}>
        📌 {result.real_fact}
      </div>
      {result.source && (
        <p style={{ fontSize: "0.76rem", color: "#64748B", margin: 0 }}>
          🔗 {result.source}
        </p>
      )}
    </div>
  );
}

function Spinner() {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "10px", color: "#0891B2", fontSize: "0.92rem" }}>
      <div style={{
        width: 18, height: 18, border: "2px solid #E0F2FE",
        borderTop: "2px solid #0891B2", borderRadius: "50%",
        animation: "spin 0.8s linear infinite",
      }} />
      <span>Working...</span>
    </div>
  );
}

export default function FactCheckApp() {
  const [file, setFile]         = useState(null);
  const [stage, setStage]       = useState("idle"); // idle | extracting | verifying | done | error
  const [results, setResults]   = useState([]);
  const [stepMsg, setStepMsg]   = useState("");
  const [errMsg, setErrMsg]     = useState("");
  const fileRef                 = useRef();

  const handleFile = (f) => {
    if (f && f.type === "application/pdf") setFile(f);
    else alert("Please upload a PDF file.");
  };

  const toBase64 = (f) => new Promise((res, rej) => {
    const r = new FileReader();
    r.onload  = () => res(r.result.split(",")[1]);
    r.onerror = () => rej(new Error("File read failed"));
    r.readAsDataURL(f);
  });

  const callClaude = async (body) => {
    const resp = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!resp.ok) throw new Error(`API error ${resp.status}: ${await resp.text()}`);
    return resp.json();
  };

  const runFactCheck = async () => {
    if (!file) return;
    setStage("extracting");
    setStepMsg("Reading document and extracting verifiable claims...");
    setResults([]);
    setErrMsg("");

    try {
      const b64 = await toBase64(file);

      // ── Step 1: Extract claims ──
      const extractData = await callClaude({
        model: "claude-sonnet-4-6",
        max_tokens: 2000,
        messages: [{
          role: "user",
          content: [
            { type: "document", source: { type: "base64", media_type: "application/pdf", data: b64 } },
            { type: "text", text:
              "You are a precise fact-extractor. Read this document and identify every specific, verifiable factual claim. " +
              "Focus on: statistics, percentages, dates, financial figures, technical specs, named research findings, any concrete numbers.\n\n" +
              "Return ONLY a valid JSON array — absolutely no preamble, no markdown fences:\n" +
              '[{"id":1,"claim":"exact claim text","category":"statistic|date|financial|technical|other","context":"one sentence context"}]\n\n' +
              "Extract 5-12 of the most specific, checkable claims. No vague statements."
            },
          ],
        }],
      });

      let claims;
      try {
        let raw = extractData.content[0].text.trim().replace(/```json|```/g, "").trim();
        claims = JSON.parse(raw);
      } catch {
        throw new Error("Could not parse claims from document. Try a different PDF.");
      }

      setStepMsg(`Found ${claims.length} claims. Searching the web to verify each one...`);
      setStage("verifying");

      // ── Step 2: Verify with web search ──
      const verifyData = await callClaude({
        model: "claude-sonnet-4-6",
        max_tokens: 4000,
        tools: [{ type: "web_search_20250305", name: "web_search" }],
        messages: [{
          role: "user",
          content:
            "You are an expert fact-checker with live web search access. Verify each claim below against current, authoritative sources.\n\n" +
            "Claims:\n" + JSON.stringify(claims, null, 2) + "\n\n" +
            "For EVERY claim, search the web, then return a JSON array:\n" +
            '[{"id":1,"claim":"original claim","status":"Verified|Inaccurate|Unverifiable",' +
            '"verdict":"one sentence explanation","real_fact":"correct current data or confirmation","source":"URL or source name"}]\n\n' +
            "Status rules:\n" +
            "- Verified: live data confirms the claim\n" +
            "- Inaccurate: live data contradicts it (wrong number, outdated stat, false claim)\n" +
            "- Unverifiable: no reliable sources found\n\n" +
            "Return ONLY the JSON array. No other text at all.",
        }],
      });

      let verified;
      try {
        const textBlock = [...verifyData.content].reverse().find(b => b.type === "text");
        let raw = textBlock.text.trim().replace(/```json|```/g, "").trim();
        verified = JSON.parse(raw);
      } catch {
        throw new Error("Could not parse verification results. Please try again.");
      }

      // Sort: Inaccurate first, then Unverifiable, then Verified
      const order = { Inaccurate: 0, Unverifiable: 1, Verified: 2 };
      verified.sort((a, b) => (order[a.status] ?? 1) - (order[b.status] ?? 1));

      setResults(verified);
      setStage("done");

    } catch (e) {
      setErrMsg(e.message || "An unexpected error occurred.");
      setStage("error");
    }
  };

  const verified_n     = results.filter(r => r.status === "Verified").length;
  const inaccurate_n   = results.filter(r => r.status === "Inaccurate").length;
  const unverifiable_n = results.filter(r => r.status === "Unverifiable").length;

  return (
    <div style={{ fontFamily: "'Inter', system-ui, sans-serif", maxWidth: 800, margin: "0 auto", padding: "1.5rem 1rem" }}>
      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes fadeIn { from { opacity:0; transform:translateY(8px); } to { opacity:1; transform:translateY(0); } }
      `}</style>

      {/* Header */}
      <div style={{ marginBottom: "1.5rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "4px" }}>
          <span style={{ fontSize: "1.8rem" }}>🔍</span>
          <h1 style={{ margin: 0, fontSize: "1.7rem", fontWeight: 700, color: "#0F172A" }}>FactCheck AI</h1>
          <span style={{ background: "#0891B2", color: "#fff", borderRadius: "20px", padding: "2px 10px", fontSize: "0.72rem", fontWeight: 600 }}>
            DEMO
          </span>
        </div>
        <p style={{ margin: 0, color: "#475569", fontSize: "0.92rem" }}>
          Upload a PDF — Claude extracts every factual claim and cross-references it against live web data.
        </p>
      </div>

      {/* Upload zone */}
      <div
        onClick={() => fileRef.current.click()}
        onDragOver={e => e.preventDefault()}
        onDrop={e => { e.preventDefault(); handleFile(e.dataTransfer.files[0]); }}
        style={{
          border: `2px dashed ${file ? "#0891B2" : "#CBD5E1"}`,
          borderRadius: "12px",
          padding: "1.8rem",
          textAlign: "center",
          cursor: "pointer",
          background: file ? "#E0F2FE" : "#F8FAFC",
          marginBottom: "1rem",
          transition: "all 0.2s",
        }}
      >
        <input ref={fileRef} type="file" accept=".pdf" style={{ display: "none" }}
          onChange={e => handleFile(e.target.files[0])} />
        {file ? (
          <div>
            <div style={{ fontSize: "1.4rem", marginBottom: "4px" }}>📄</div>
            <strong style={{ color: "#0369A1" }}>{file.name}</strong>
            <div style={{ fontSize: "0.8rem", color: "#64748B" }}>{(file.size / 1024).toFixed(1)} KB · Click to replace</div>
          </div>
        ) : (
          <div>
            <div style={{ fontSize: "1.6rem", marginBottom: "6px" }}>☁️</div>
            <div style={{ fontWeight: 600, color: "#334155" }}>Drop a PDF here or click to browse</div>
            <div style={{ fontSize: "0.8rem", color: "#64748B", marginTop: "4px" }}>Supports any PDF up to 10 MB</div>
          </div>
        )}
      </div>

      {/* Run button */}
      <button
        onClick={runFactCheck}
        disabled={!file || stage === "extracting" || stage === "verifying"}
        style={{
          width: "100%", padding: "0.8rem",
          background: (!file || stage === "extracting" || stage === "verifying") ? "#94A3B8" : "#0891B2",
          color: "#fff", border: "none", borderRadius: "8px",
          fontSize: "1rem", fontWeight: 600, cursor: "pointer",
          marginBottom: "1.5rem", transition: "background 0.2s",
        }}
      >
        {stage === "extracting" || stage === "verifying" ? "Checking..." : "Run Fact Check →"}
      </button>

      {/* Status */}
      {(stage === "extracting" || stage === "verifying") && (
        <div style={{ background: "#F0F9FF", border: "1px solid #BAE6FD", borderRadius: "8px", padding: "1rem", marginBottom: "1.2rem" }}>
          <Spinner />
          <p style={{ margin: "8px 0 0", fontSize: "0.87rem", color: "#0369A1" }}>{stepMsg}</p>
        </div>
      )}

      {stage === "error" && (
        <div style={{ background: "#FEF2F2", border: "1px solid #FECACA", borderRadius: "8px", padding: "1rem", marginBottom: "1.2rem", color: "#991B1B" }}>
          <strong>Error:</strong> {errMsg}
        </div>
      )}

      {/* Results */}
      {stage === "done" && results.length > 0 && (
        <div>
          {/* Summary stats */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "0.75rem", marginBottom: "1.2rem" }}>
            {[
              { n: results.length, label: "Claims Checked",          color: "#0F172A" },
              { n: verified_n,     label: "Verified",                 color: "#10B981" },
              { n: inaccurate_n,   label: "Inaccurate / Outdated",    color: "#EF4444" },
              { n: unverifiable_n, label: "Unverifiable",             color: "#F59E0B" },
            ].map((s, i) => (
              <div key={i} style={{ background: "#F8FAFC", border: "1px solid #E2E8F0", borderRadius: "10px", padding: "0.9rem", textAlign: "center" }}>
                <div style={{ fontSize: "1.8rem", fontWeight: 700, color: s.color }}>{s.n}</div>
                <div style={{ fontSize: "0.75rem", color: "#64748B", marginTop: "2px" }}>{s.label}</div>
              </div>
            ))}
          </div>

          <h2 style={{ fontSize: "1.1rem", fontWeight: 700, color: "#0F172A", marginBottom: "0.8rem" }}>
            Detailed Results {inaccurate_n > 0 && <span style={{ color: "#EF4444", fontSize: "0.85rem" }}>({inaccurate_n} problem{inaccurate_n > 1 ? "s" : ""} found)</span>}
          </h2>

          {results.map((r, i) => <ClaimCard key={r.id} result={r} index={i} />)}

          <div style={{ textAlign: "center", paddingTop: "1rem", color: "#94A3B8", fontSize: "0.8rem" }}>
            Powered by Claude Sonnet 4.6 + Web Search · Results reflect live web data at time of check
          </div>
        </div>
      )}
    </div>
  );
        }
