import { useEffect, useState } from "react";
import { api } from "../api/client";
import Badge from "../components/Badge";

export default function Analytics() {
  const [a, setA] = useState(null);

  useEffect(() => {
    api.get("/analytics").then(setA);
  }, []);

  if (!a) return null;

  return (
    <div>
      <h2>📈 Analytics & Reporting</h2>
      <div className="stat-grid">
        <div className="stat-card"><div className="stat-num">{a.total_submissions}</div><div className="stat-lbl">Total</div></div>
        <div className="stat-card"><div className="stat-num">{a.by_status.approved || 0}</div><div className="stat-lbl">Approved</div></div>
        <div className="stat-card"><div className="stat-num">{a.by_status.rejected || 0}</div><div className="stat-lbl">Rejected</div></div>
        <div className="stat-card"><div className="stat-num">{a.pending}</div><div className="stat-lbl">Pending</div></div>
        <div className="stat-card"><div className="stat-num">{a.total_conflicts}</div><div className="stat-lbl">Conflicts</div></div>
      </div>
      <hr className="divider" />
      <div className="row">
        <div>
          <h3>By Status</h3>
          {Object.entries(a.by_status).map(([status, cnt]) => {
            const pct = Math.round((cnt / Math.max(a.total_submissions, 1)) * 100);
            return (
              <div key={status} style={{ marginBottom: 8 }}>
                <Badge status={status} /> {cnt} ({pct}%)
              </div>
            );
          })}
        </div>
        <div>
          <h3>Top Issues</h3>
          {a.top_regulations.map((r, i) => (
            <div key={i} style={{ marginBottom: 6 }}>
              <Badge status={r.severity} /> <strong>{r.regulation}</strong> — {r.cnt}×
            </div>
          ))}
        </div>
      </div>
      <hr className="divider" />
      <h3>📥 Export</h3>
      <div className="row">
        <button onClick={() => api.downloadJson("/analytics/export/submissions", "submissions.json")}>⬇️ Submissions (JSON)</button>
        <button onClick={() => api.downloadJson("/analytics", "analytics.json")}>⬇️ Analytics (JSON)</button>
        <button onClick={() => api.downloadJson("/analytics/export/audit-log", "audit_log.json")}>⬇️ Audit Log (JSON)</button>
      </div>
    </div>
  );
}
