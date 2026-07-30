import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import Badge from "../components/Badge";

export default function MySubmissions() {
  const [subs, setSubs] = useState(null);

  useEffect(() => {
    api.get("/submissions?mine=true").then((d) => setSubs(d.submissions));
  }, []);

  if (!subs) return null;

  return (
    <div>
      <h2>📋 My Submissions</h2>
      {subs.length === 0 && (
        <div className="alert alert-info">No submissions yet. <Link to="/submit">Submit your first document</Link>.</div>
      )}
      {subs.map((s) => (
        <div className="list-row" key={s.id}>
          <div>
            <strong>{s.title}</strong>
            <div className="muted">{s.submitted_at.slice(0, 10)} · {s.product || "general"}</div>
          </div>
          <Badge status={s.status} />
          <Link to={`/submissions/${s.id}`} className="btn">View</Link>
        </div>
      ))}
    </div>
  );
}
