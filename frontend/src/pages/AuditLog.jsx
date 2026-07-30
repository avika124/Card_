import { useEffect, useState } from "react";
import { api } from "../api/client";

const ICONS = {
  login: "🔐", logout: "🚪", submit: "📤", review_decision: "✅",
  mark_false_positive: "☑️", add_company_memory: "🏢", add_reg_watch: "🛰️",
  regulatory_change_detected: "⚠️",
};

export default function AuditLog() {
  const [logs, setLogs] = useState(null);

  useEffect(() => {
    api.get("/audit-log?limit=200").then((d) => setLogs(d.entries));
  }, []);

  if (!logs) return null;

  return (
    <div>
      <h2>📜 Audit Log</h2>
      {logs.length === 0 && <div className="alert alert-info">No entries yet.</div>}
      {logs.map((e) => (
        <div key={e.id} style={{ marginBottom: 10 }}>
          {ICONS[e.action] || "📋"} <strong>{e.action.replace(/_/g, " ")}</strong> · {e.user_email || "system"} · {(e.timestamp || "").slice(0, 16).replace("T", " ")}
          {e.detail && <div className="muted">{e.detail}</div>}
          <hr className="divider" />
        </div>
      ))}
    </div>
  );
}
