import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";
import Badge from "../components/Badge";

const SEV_ORDER = { high: 0, medium: 1, low: 2, pass: 3 };
const DECISION_ICON = { approved: "✅", rejected: "❌", escalated: "⚠️", in_review: "👀" };

export default function ReviewDetail() {
  const { id } = useParams();
  const { isRole } = useAuth();
  const [data, setData] = useState(null);
  const [tab, setTab] = useState("findings");
  const [decision, setDecision] = useState("approved");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const canReview = isRole("compliance", "legal", "admin");

  function load() {
    api.get(`/submissions/${id}`).then(setData).catch((e) => setError(e.message));
  }

  useEffect(load, [id]);

  async function flagFalsePositive(kind, itemId) {
    await api.post(`/${kind}/${itemId}/false-positive`, {});
    load();
  }

  async function submitDecision(e) {
    e.preventDefault();
    if (["rejected", "escalated"].includes(decision) && !notes.trim()) {
      setError("Notes are required for reject/escalate.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await api.post(`/submissions/${id}/review`, { decision, notes });
      setNotes("");
      load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  if (error && !data) return <div className="alert alert-error">{error}</div>;
  if (!data) return null;

  const { submission: sub, findings, conflicts, reviews } = data;
  const highF = findings.filter((f) => f.severity === "high" && !f.is_false_positive).length;
  const medF = findings.filter((f) => f.severity === "medium" && !f.is_false_positive).length;
  const sortedFindings = [...findings].sort((a, b) => (SEV_ORDER[a.severity] ?? 2) - (SEV_ORDER[b.severity] ?? 2));

  return (
    <div>
      <div className="row" style={{ alignItems: "flex-start" }}>
        <div style={{ flex: 3 }}>
          <h2>{sub.title}</h2>
          <p className="muted">{sub.submitter_name || "?"} · {sub.submitted_at.slice(0, 16).replace("T", " ")}</p>
        </div>
        <div style={{ flex: 1, textAlign: "right" }}>
          <Badge status={sub.status} />
          <div style={{ marginTop: 8 }}>
            <button onClick={() => api.downloadDocx(`/submissions/${id}/docx`, `report_${id.slice(0, 8)}.docx`)}>⬇️ DOCX</button>
          </div>
        </div>
      </div>

      <div className="stat-grid">
        <div className="stat-card"><div className="stat-num">{highF}</div><div className="stat-lbl">High Risk</div></div>
        <div className="stat-card"><div className="stat-num">{medF}</div><div className="stat-lbl">Med Risk</div></div>
        <div className="stat-card"><div className="stat-num">{conflicts.length}</div><div className="stat-lbl">Conflicts</div></div>
        <div className="stat-card"><div className="stat-num">{reviews.length}</div><div className="stat-lbl">Reviews</div></div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      <div className="tabs">
        <button className={`tab${tab === "findings" ? " active" : ""}`} onClick={() => setTab("findings")}>📋 Findings ({findings.length})</button>
        <button className={`tab${tab === "conflicts" ? " active" : ""}`} onClick={() => setTab("conflicts")}>🏢 Conflicts ({conflicts.length})</button>
        <button className={`tab${tab === "review" ? " active" : ""}`} onClick={() => setTab("review")}>✅ Review</button>
        <button className={`tab${tab === "document" ? " active" : ""}`} onClick={() => setTab("document")}>📄 Document</button>
        <button className={`tab${tab === "history" ? " active" : ""}`} onClick={() => setTab("history")}>📜 History ({reviews.length})</button>
      </div>

      {tab === "findings" && (
        <div>
          {sortedFindings.length === 0 && <div className="alert alert-success">No regulatory findings.</div>}
          {sortedFindings.map((f) => (
            <div className={`finding-row finding-${f.severity}`} style={f.is_false_positive ? { opacity: 0.4 } : {}} key={f.id}>
              <Badge status={f.severity} /> <strong>{f.regulation}</strong> · {f.issue}
              {!!f.is_false_positive && <em style={{ color: "#999", fontSize: 11 }}> (false positive)</em>}
              <div style={{ marginTop: 6 }}>{f.detail}</div>
              {f.regulatory_citation && <code style={{ display: "block", marginTop: 4 }}>{f.regulatory_citation}</code>}
              {f.excerpt && <div className="alert alert-info" style={{ marginTop: 6 }}>📌 "{f.excerpt}"</div>}
              {f.recommendation && <div className="alert alert-success" style={{ marginTop: 6 }}>{f.recommendation}</div>}
              {canReview && !f.is_false_positive && (
                <button style={{ marginTop: 6 }} onClick={() => flagFalsePositive("findings", f.id)}>Mark false positive</button>
              )}
            </div>
          ))}
        </div>
      )}

      {tab === "conflicts" && (
        <div>
          {conflicts.length === 0 && <div className="alert alert-success">No conflicts with prior communications.</div>}
          {conflicts.map((c) => (
            <div className="card" key={c.id} style={c.is_false_positive ? { opacity: 0.4 } : {}}>
              <Badge status={c.severity} /> <strong>{c.title}</strong>
              <div className="row" style={{ marginTop: 8 }}>
                <div>
                  <strong>New doc says:</strong>
                  <div className="alert alert-error">{c.new_doc_says}</div>
                </div>
                <div>
                  <strong>Prior says</strong> <span className="muted">(from: {c.prior_source})</span>
                  <div className="alert alert-info">{c.prior_says}</div>
                </div>
              </div>
              <div className="alert alert-error">{c.explanation}</div>
              <div className="alert alert-success">{c.recommendation}</div>
              {canReview && !c.is_false_positive && (
                <button onClick={() => flagFalsePositive("conflicts", c.id)}>Mark false positive</button>
              )}
            </div>
          ))}
        </div>
      )}

      {tab === "review" && (
        canReview ? (
          <form onSubmit={submitDecision}>
            <div className="field">
              <label>Decision</label>
              <select value={decision} onChange={(e) => setDecision(e.target.value)}>
                <option value="approved">✅ Approve</option>
                <option value="rejected">❌ Reject</option>
                <option value="escalated">⚠️ Escalate</option>
                <option value="in_review">👀 In Review</option>
              </select>
            </div>
            <div className="field">
              <label>Notes</label>
              <textarea rows={4} value={notes} onChange={(e) => setNotes(e.target.value)} />
            </div>
            <button className="btn-primary" type="submit" disabled={busy}>Submit Decision</button>
          </form>
        ) : (
          reviews.length > 0 ? (
            <div>
              <strong>Latest:</strong> {reviews[0].decision.toUpperCase()} by {reviews[0].reviewer_name || "?"}
              {reviews[0].notes && <p>{reviews[0].notes}</p>}
            </div>
          ) : <div className="alert alert-info">No decision yet.</div>
        )
      )}

      {tab === "document" && (
        <textarea rows={18} readOnly value={sub.document_text} />
      )}

      {tab === "history" && (
        <div>
          {reviews.length === 0 && <div className="alert alert-info">No history.</div>}
          {reviews.map((r) => (
            <div key={r.id} style={{ marginBottom: 12 }}>
              {DECISION_ICON[r.decision] || "📋"} <strong>{r.decision.toUpperCase()}</strong> by {r.reviewer_name || "?"} · {r.reviewed_at.slice(0, 16).replace("T", " ")}
              {r.notes && <p>{r.notes}</p>}
              <hr className="divider" />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
