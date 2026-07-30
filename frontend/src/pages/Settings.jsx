import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";

export default function Settings() {
  const { user } = useAuth();
  const [tab, setTab] = useState("users");
  const [users, setUsers] = useState([]);
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [role, setRole] = useState("submitter");
  const [department, setDepartment] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [slackStatus, setSlackStatus] = useState("");

  function refresh() {
    api.get("/auth/users").then((d) => setUsers(d.users));
  }

  useEffect(refresh, []);

  async function addUser(e) {
    e.preventDefault();
    setError(""); setSuccess("");
    try {
      await api.post("/auth/users", { email, name, role, department, password });
      setSuccess(`Created: ${email}`);
      setEmail(""); setName(""); setDepartment(""); setPassword("");
      refresh();
    } catch (err) {
      setError(err.message);
    }
  }

  async function testSlack() {
    setSlackStatus("Sending…");
    try {
      const res = await api.post("/settings/test-slack", {});
      setSlackStatus(res.ok ? "✅ Sent!" : "❌ Failed. Check SLACK_WEBHOOK_URL in .env");
    } catch (err) {
      setSlackStatus(err.message);
    }
  }

  return (
    <div>
      <h2>⚙️ Settings</h2>
      <div className="tabs">
        <button className={`tab${tab === "users" ? " active" : ""}`} onClick={() => setTab("users")}>👥 Users</button>
        <button className={`tab${tab === "notifications" ? " active" : ""}`} onClick={() => setTab("notifications")}>🔔 Notifications</button>
        <button className={`tab${tab === "company" ? " active" : ""}`} onClick={() => setTab("company")}>🏢 Company</button>
      </div>

      {tab === "users" && (
        <div>
          {users.map((u) => (
            <div className="list-row" key={u.id}>
              <div>
                <strong>{u.name}</strong> · {u.email}
                <div className="muted">{u.role.toUpperCase()} · {u.department || ""}</div>
              </div>
              <span>{u.is_active ? "✅ Active" : "⏸️ Inactive"}</span>
            </div>
          ))}
          <hr className="divider" />
          <h3>Add User</h3>
          {error && <div className="alert alert-error">{error}</div>}
          {success && <div className="alert alert-success">{success}</div>}
          <form onSubmit={addUser}>
            <div className="row">
              <div className="field"><label>Email</label><input value={email} onChange={(e) => setEmail(e.target.value)} /></div>
              <div className="field"><label>Name</label><input value={name} onChange={(e) => setName(e.target.value)} /></div>
            </div>
            <div className="row">
              <div className="field">
                <label>Role</label>
                <select value={role} onChange={(e) => setRole(e.target.value)}>
                  <option value="submitter">Submitter</option>
                  <option value="compliance">Compliance</option>
                  <option value="legal">Legal</option>
                  <option value="admin">Admin</option>
                </select>
              </div>
              <div className="field"><label>Department</label><input value={department} onChange={(e) => setDepartment(e.target.value)} /></div>
            </div>
            <div className="field"><label>Password</label><input type="password" value={password} onChange={(e) => setPassword(e.target.value)} /></div>
            <button className="btn-primary" type="submit">Add User</button>
          </form>
        </div>
      )}

      {tab === "notifications" && (
        <div>
          <p className="muted">Add SLACK_WEBHOOK_URL, SMTP_HOST, SMTP_USER, SMTP_PASSWORD, FROM_EMAIL to the backend's .env to configure notifications.</p>
          <button onClick={testSlack}>🧪 Test Slack</button>
          {slackStatus && <div className="alert alert-info" style={{ marginTop: 8 }}>{slackStatus}</div>}
        </div>
      )}

      {tab === "company" && (
        <div>
          <p><strong>Company:</strong> {user.company}</p>
          <p><strong>Your role:</strong> {user.role.toUpperCase()}</p>
        </div>
      )}
    </div>
  );
}
