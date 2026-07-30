import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await login(email, password);
      navigate("/");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-shell">
      <div className="login-card">
        <div style={{ textAlign: "center", marginBottom: 24 }}>
          <h1 style={{ marginBottom: 4 }}>⚖️ Compliance Platform</h1>
          <p className="muted">Credit Card Regulatory Compliance</p>
        </div>
        {error && <div className="alert alert-error">{error}</div>}
        <form onSubmit={onSubmit}>
          <div className="field">
            <label>Email</label>
            <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="compliance@company.com" required />
          </div>
          <div className="field">
            <label>Password</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </div>
          <button className="btn-primary" style={{ width: "100%" }} disabled={busy} type="submit">
            {busy ? "Signing in…" : "Sign In"}
          </button>
        </form>
        <div className="alert alert-info" style={{ marginTop: 16 }}>
          <strong>Demo accounts</strong> (all passwords: password123)<br />
          admin@company.com · compliance@company.com · legal@company.com · marketing@company.com
        </div>
      </div>
    </div>
  );
}
