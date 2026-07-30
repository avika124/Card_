import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import Badge from "../components/Badge";

export default function AllReviews() {
  const [subs, setSubs] = useState(null);

  useEffect(() => {
    api.get("/submissions").then((d) =>
      setSubs(d.submissions.filter((s) => ["approved", "rejected", "escalated"].includes(s.status)))
    );
  }, []);

  if (!subs) return null;

  return (
    <div>
      <h2>✅ All Reviews</h2>
      {subs.length === 0 && <div className="alert alert-info">No reviewed submissions yet.</div>}
      {subs.map((s) => (
        <div className="list-row" key={s.id}>
          <div>
            <strong>{s.title}</strong>
            <div className="muted">{s.submitter_name || "?"}</div>
          </div>
          <Badge status={s.status} />
          <Link to={`/submissions/${s.id}`} className="btn">View</Link>
        </div>
      ))}
    </div>
  );
}
