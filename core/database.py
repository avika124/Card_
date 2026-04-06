"""
core/database.py — SQLite persistence layer

Tables:
  users          - multi-tenant users with roles
  submissions    - documents submitted for review
  findings       - compliance findings per submission
  conflicts      - prior-comm conflict findings per submission
  reviews        - compliance officer review decisions
  audit_log      - every action with timestamp + user
  notifications  - pending alerts
  reg_watches    - regulatory change monitoring subscriptions
  analytics      - aggregated stats cache
"""

import sqlite3
import json
import hashlib
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

DB_PATH = str(Path(__file__).parent.parent / "data" / "compliance.db")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()


@contextmanager
def get_db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create all tables if they don't exist."""
    with get_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id          TEXT PRIMARY KEY,
            email       TEXT UNIQUE NOT NULL,
            name        TEXT NOT NULL,
            role        TEXT NOT NULL DEFAULT 'submitter',
            company     TEXT NOT NULL DEFAULT 'Default',
            department  TEXT DEFAULT '',
            password_hash TEXT NOT NULL,
            salt        TEXT NOT NULL,
            created_at  TEXT NOT NULL,
            last_login  TEXT,
            is_active   INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS submissions (
            id              TEXT PRIMARY KEY,
            title           TEXT NOT NULL,
            document_text   TEXT NOT NULL,
            document_name   TEXT DEFAULT '',
            doc_type        TEXT DEFAULT 'marketing',
            product         TEXT DEFAULT 'general',
            channel         TEXT DEFAULT 'general',
            submitted_by    TEXT NOT NULL,
            company         TEXT NOT NULL,
            status          TEXT DEFAULT 'pending',
            priority        TEXT DEFAULT 'normal',
            regulations     TEXT DEFAULT '[]',
            run_conflict    INTEGER DEFAULT 1,
            submitted_at    TEXT NOT NULL,
            reviewed_at     TEXT,
            reviewed_by     TEXT,
            FOREIGN KEY(submitted_by) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS findings (
            id              TEXT PRIMARY KEY,
            submission_id   TEXT NOT NULL,
            regulation      TEXT NOT NULL,
            severity        TEXT NOT NULL,
            issue           TEXT NOT NULL,
            detail          TEXT NOT NULL,
            regulatory_citation TEXT DEFAULT '',
            excerpt         TEXT DEFAULT '',
            recommendation  TEXT DEFAULT '',
            is_false_positive INTEGER DEFAULT 0,
            reviewed_by     TEXT,
            reviewed_at     TEXT,
            FOREIGN KEY(submission_id) REFERENCES submissions(id)
        );

        CREATE TABLE IF NOT EXISTS conflicts (
            id              TEXT PRIMARY KEY,
            submission_id   TEXT NOT NULL,
            severity        TEXT NOT NULL,
            category        TEXT NOT NULL,
            title           TEXT NOT NULL,
            new_doc_says    TEXT NOT NULL,
            prior_says      TEXT NOT NULL,
            prior_source    TEXT NOT NULL,
            explanation     TEXT NOT NULL,
            recommendation  TEXT NOT NULL,
            is_false_positive INTEGER DEFAULT 0,
            FOREIGN KEY(submission_id) REFERENCES submissions(id)
        );

        CREATE TABLE IF NOT EXISTS reviews (
            id              TEXT PRIMARY KEY,
            submission_id   TEXT NOT NULL,
            reviewer_id     TEXT NOT NULL,
            decision        TEXT NOT NULL,
            notes           TEXT DEFAULT '',
            reviewed_at     TEXT NOT NULL,
            FOREIGN KEY(submission_id) REFERENCES submissions(id),
            FOREIGN KEY(reviewer_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id          TEXT PRIMARY KEY,
            user_id     TEXT,
            user_email  TEXT,
            action      TEXT NOT NULL,
            entity_type TEXT DEFAULT '',
            entity_id   TEXT DEFAULT '',
            detail      TEXT DEFAULT '',
            ip_address  TEXT DEFAULT '',
            timestamp   TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS notifications (
            id              TEXT PRIMARY KEY,
            user_id         TEXT NOT NULL,
            type            TEXT NOT NULL,
            title           TEXT NOT NULL,
            message         TEXT NOT NULL,
            link            TEXT DEFAULT '',
            is_read         INTEGER DEFAULT 0,
            created_at      TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS reg_watches (
            id          TEXT PRIMARY KEY,
            company     TEXT NOT NULL,
            regulation  TEXT NOT NULL,
            source_url  TEXT NOT NULL,
            source_name TEXT NOT NULL,
            last_content_hash TEXT DEFAULT '',
            last_checked    TEXT,
            created_by  TEXT NOT NULL,
            is_active   INTEGER DEFAULT 1,
            created_at  TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_submissions_company ON submissions(company);
        CREATE INDEX IF NOT EXISTS idx_submissions_status ON submissions(status);
        CREATE INDEX IF NOT EXISTS idx_findings_submission ON findings(submission_id);
        CREATE INDEX IF NOT EXISTS idx_conflicts_submission ON conflicts(submission_id);
        CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
        CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id, is_read);
        """)

    # Create default admin if no users exist
    with get_db() as db:
        count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if count == 0:
            _create_default_users(db)


def _create_default_users(db):
    """Seed default demo users."""
    import uuid
    users = [
        ("admin@company.com",      "Admin User",       "admin",      "Acme Financial"),
        ("compliance@company.com", "Compliance Officer","compliance", "Acme Financial"),
        ("legal@company.com",      "Legal Counsel",    "legal",      "Acme Financial"),
        ("marketing@company.com",  "Marketing Manager","submitter",  "Acme Financial"),
    ]
    for email, name, role, company in users:
        uid = str(uuid.uuid4())
        salt = secrets.token_hex(16)
        pw_hash = _hash_password("password123", salt)
        db.execute(
            "INSERT INTO users(id,email,name,role,company,department,password_hash,salt,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (uid, email, name, role, company, role.title(), pw_hash, salt, _now())
        )


# ── User functions ─────────────────────────────────────────────────────────────

def authenticate_user(email: str, password: str) -> Optional[dict]:
    with get_db() as db:
        row = db.execute("SELECT * FROM users WHERE email=? AND is_active=1", (email,)).fetchone()
        if not row:
            return None
        if _hash_password(password, row["salt"]) != row["password_hash"]:
            return None
        db.execute("UPDATE users SET last_login=? WHERE id=?", (_now(), row["id"]))
        return dict(row)


def create_user(email, name, role, company, department, password) -> str:
    import uuid
    uid = str(uuid.uuid4())
    salt = secrets.token_hex(16)
    pw_hash = _hash_password(password, salt)
    with get_db() as db:
        db.execute(
            "INSERT INTO users(id,email,name,role,company,department,password_hash,salt,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (uid, email, name, role, company, department, pw_hash, salt, _now())
        )
    return uid


def get_users(company: Optional[str] = None) -> list:
    with get_db() as db:
        if company:
            rows = db.execute("SELECT * FROM users WHERE company=? ORDER BY name", (company,)).fetchall()
        else:
            rows = db.execute("SELECT * FROM users ORDER BY company, name").fetchall()
        return [dict(r) for r in rows]


# ── Submission functions ───────────────────────────────────────────────────────

def create_submission(title, document_text, document_name, doc_type, product,
                       channel, submitted_by, company, regulations,
                       run_conflict=True, priority="normal") -> str:
    import uuid
    sid = str(uuid.uuid4())
    with get_db() as db:
        db.execute(
            """INSERT INTO submissions(id,title,document_text,document_name,doc_type,product,
               channel,submitted_by,company,status,priority,regulations,run_conflict,submitted_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (sid, title, document_text, document_name, doc_type, product,
             channel, submitted_by, company, "pending", priority,
             json.dumps(regulations), 1 if run_conflict else 0, _now())
        )
    return sid


def get_submissions(company: str, status: Optional[str] = None,
                    submitted_by: Optional[str] = None) -> list:
    with get_db() as db:
        query = "SELECT s.*, u.name as submitter_name, u.email as submitter_email FROM submissions s LEFT JOIN users u ON s.submitted_by=u.id WHERE s.company=?"
        params = [company]
        if status:
            query += " AND s.status=?"; params.append(status)
        if submitted_by:
            query += " AND s.submitted_by=?"; params.append(submitted_by)
        query += " ORDER BY s.submitted_at DESC"
        return [dict(r) for r in db.execute(query, params).fetchall()]


def get_submission(submission_id: str) -> Optional[dict]:
    with get_db() as db:
        row = db.execute(
            "SELECT s.*, u.name as submitter_name FROM submissions s LEFT JOIN users u ON s.submitted_by=u.id WHERE s.id=?",
            (submission_id,)
        ).fetchone()
        return dict(row) if row else None


def update_submission_status(submission_id: str, status: str,
                              reviewed_by: Optional[str] = None):
    with get_db() as db:
        if reviewed_by:
            db.execute("UPDATE submissions SET status=?, reviewed_at=?, reviewed_by=? WHERE id=?",
                       (status, _now(), reviewed_by, submission_id))
        else:
            db.execute("UPDATE submissions SET status=? WHERE id=?", (status, submission_id))


def save_findings(submission_id: str, findings: list):
    import uuid
    with get_db() as db:
        db.execute("DELETE FROM findings WHERE submission_id=?", (submission_id,))
        for f in findings:
            db.execute(
                """INSERT INTO findings(id,submission_id,regulation,severity,issue,detail,
                   regulatory_citation,excerpt,recommendation) VALUES(?,?,?,?,?,?,?,?,?)""",
                (str(uuid.uuid4()), submission_id, f.get("regulation",""),
                 f.get("severity","low"), f.get("issue",""), f.get("detail",""),
                 f.get("regulatory_citation",""), f.get("excerpt",""),
                 f.get("recommendation",""))
            )


def save_conflicts(submission_id: str, conflicts: list):
    import uuid
    with get_db() as db:
        db.execute("DELETE FROM conflicts WHERE submission_id=?", (submission_id,))
        for c in conflicts:
            db.execute(
                """INSERT INTO conflicts(id,submission_id,severity,category,title,
                   new_doc_says,prior_says,prior_source,explanation,recommendation)
                   VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (str(uuid.uuid4()), submission_id, c.get("severity","low"),
                 c.get("category",""), c.get("title",""),
                 c.get("new_document_says",""), c.get("prior_communication_says",""),
                 c.get("prior_source",""), c.get("explanation",""),
                 c.get("recommendation",""))
            )


def get_findings(submission_id: str) -> list:
    with get_db() as db:
        return [dict(r) for r in db.execute(
            "SELECT * FROM findings WHERE submission_id=? ORDER BY CASE severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 WHEN 'low' THEN 2 ELSE 3 END",
            (submission_id,)
        ).fetchall()]


def get_conflicts(submission_id: str) -> list:
    with get_db() as db:
        return [dict(r) for r in db.execute(
            "SELECT * FROM conflicts WHERE submission_id=? ORDER BY CASE severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END",
            (submission_id,)
        ).fetchall()]


def mark_false_positive(finding_id: str, table: str, reviewer: str):
    with get_db() as db:
        if table == "findings":
            db.execute("UPDATE findings SET is_false_positive=1, reviewed_by=?, reviewed_at=? WHERE id=?",
                       (reviewer, _now(), finding_id))
        else:
            db.execute("UPDATE conflicts SET is_false_positive=1 WHERE id=?", (finding_id,))


# ── Review functions ───────────────────────────────────────────────────────────

def create_review(submission_id, reviewer_id, decision, notes="") -> str:
    import uuid
    rid = str(uuid.uuid4())
    with get_db() as db:
        db.execute(
            "INSERT INTO reviews(id,submission_id,reviewer_id,decision,notes,reviewed_at) VALUES(?,?,?,?,?,?)",
            (rid, submission_id, reviewer_id, decision, notes, _now())
        )
    update_submission_status(submission_id, decision, reviewed_by=reviewer_id)
    return rid


def get_reviews(submission_id: str) -> list:
    with get_db() as db:
        return [dict(r) for r in db.execute(
            "SELECT r.*, u.name as reviewer_name FROM reviews r LEFT JOIN users u ON r.reviewer_id=u.id WHERE r.submission_id=? ORDER BY r.reviewed_at DESC",
            (submission_id,)
        ).fetchall()]


# ── Audit log ──────────────────────────────────────────────────────────────────

def log_action(user_id, user_email, action, entity_type="", entity_id="", detail="", ip=""):
    import uuid
    with get_db() as db:
        db.execute(
            "INSERT INTO audit_log(id,user_id,user_email,action,entity_type,entity_id,detail,ip_address,timestamp) VALUES(?,?,?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), user_id, user_email, action, entity_type, entity_id, detail, ip, _now())
        )


def get_audit_log(company: Optional[str] = None, limit: int = 100) -> list:
    with get_db() as db:
        if company:
            rows = db.execute(
                "SELECT a.* FROM audit_log a LEFT JOIN users u ON a.user_id=u.id WHERE u.company=? OR a.user_id IS NULL ORDER BY a.timestamp DESC LIMIT ?",
                (company, limit)
            ).fetchall()
        else:
            rows = db.execute("SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]


# ── Notifications ──────────────────────────────────────────────────────────────

def create_notification(user_id, ntype, title, message, link=""):
    import uuid
    with get_db() as db:
        db.execute(
            "INSERT INTO notifications(id,user_id,type,title,message,link,created_at) VALUES(?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), user_id, ntype, title, message, link, _now())
        )


def get_notifications(user_id: str, unread_only: bool = False) -> list:
    with get_db() as db:
        query = "SELECT * FROM notifications WHERE user_id=?"
        params = [user_id]
        if unread_only:
            query += " AND is_read=0"
        query += " ORDER BY created_at DESC LIMIT 50"
        return [dict(r) for r in db.execute(query, params).fetchall()]


def mark_notifications_read(user_id: str):
    with get_db() as db:
        db.execute("UPDATE notifications SET is_read=1 WHERE user_id=?", (user_id,))


# ── Regulatory watches ─────────────────────────────────────────────────────────

def add_reg_watch(company, regulation, source_url, source_name, created_by) -> str:
    import uuid
    wid = str(uuid.uuid4())
    with get_db() as db:
        db.execute(
            "INSERT INTO reg_watches(id,company,regulation,source_url,source_name,created_by,created_at) VALUES(?,?,?,?,?,?,?)",
            (wid, company, regulation, source_url, source_name, created_by, _now())
        )
    return wid


def get_reg_watches(company: str) -> list:
    with get_db() as db:
        return [dict(r) for r in db.execute(
            "SELECT * FROM reg_watches WHERE company=? AND is_active=1 ORDER BY regulation",
            (company,)
        ).fetchall()]


def update_watch_hash(watch_id: str, content_hash: str):
    with get_db() as db:
        db.execute("UPDATE reg_watches SET last_content_hash=?, last_checked=? WHERE id=?",
                   (content_hash, _now(), watch_id))


# ── Analytics ──────────────────────────────────────────────────────────────────

def get_analytics(company: str) -> dict:
    with get_db() as db:
        total = db.execute("SELECT COUNT(*) FROM submissions WHERE company=?", (company,)).fetchone()[0]
        by_status = {r["status"]: r["cnt"] for r in db.execute(
            "SELECT status, COUNT(*) as cnt FROM submissions WHERE company=? GROUP BY status", (company,)
        ).fetchall()}
        by_risk = {r["overall_risk"]: r["cnt"] for r in db.execute(
            """SELECT CASE
                 WHEN EXISTS(SELECT 1 FROM findings f WHERE f.submission_id=s.id AND f.severity='high' AND f.is_false_positive=0) THEN 'high'
                 WHEN EXISTS(SELECT 1 FROM findings f WHERE f.submission_id=s.id AND f.severity='medium' AND f.is_false_positive=0) THEN 'medium'
                 WHEN EXISTS(SELECT 1 FROM findings f WHERE f.submission_id=s.id AND f.severity='low' AND f.is_false_positive=0) THEN 'low'
                 ELSE 'pass'
               END as overall_risk, COUNT(*) as cnt
               FROM submissions s WHERE s.company=? GROUP BY overall_risk""", (company,)
        ).fetchall()}
        top_regs = [dict(r) for r in db.execute(
            """SELECT regulation, severity, COUNT(*) as cnt
               FROM findings f JOIN submissions s ON f.submission_id=s.id
               WHERE s.company=? AND f.is_false_positive=0
               GROUP BY regulation, severity ORDER BY cnt DESC LIMIT 10""", (company,)
        ).fetchall()]
        conflict_count = db.execute(
            "SELECT COUNT(*) FROM conflicts c JOIN submissions s ON c.submission_id=s.id WHERE s.company=? AND c.is_false_positive=0",
            (company,)
        ).fetchone()[0]
        recent = [dict(r) for r in db.execute(
            "SELECT id, title, status, submitted_at FROM submissions WHERE company=? ORDER BY submitted_at DESC LIMIT 5",
            (company,)
        ).fetchall()]

        return {
            "total_submissions": total,
            "by_status": by_status,
            "by_risk": by_risk,
            "top_regulations": top_regs,
            "total_conflicts": conflict_count,
            "recent_submissions": recent,
            "pending": by_status.get("pending", 0) + by_status.get("in_review", 0),
        }
