"""
integrations/notifier.py — Slack & Email Notification Dispatcher

Sends alerts for:
  - New submission requiring review
  - Review decision (approved/rejected/escalated)
  - Regulatory change detected
  - High-risk finding
  - Prior communication conflict

Config (via environment variables):
  SLACK_WEBHOOK_URL      — Slack incoming webhook URL
  SMTP_HOST              — Email SMTP host
  SMTP_PORT              — SMTP port (default 587)
  SMTP_USER              — SMTP username
  SMTP_PASSWORD          — SMTP password
  FROM_EMAIL             — Sender email address
  APP_BASE_URL           — Base URL of the app (for deep links)
"""

import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

import requests

APP_URL = os.environ.get("APP_BASE_URL", "http://localhost:8501")


# ── Slack ──────────────────────────────────────────────────────────────────────

def send_slack(message: str, webhook_url: Optional[str] = None,
               blocks: Optional[list] = None) -> bool:
    url = webhook_url or os.environ.get("SLACK_WEBHOOK_URL")
    if not url:
        return False
    try:
        payload = {"text": message}
        if blocks:
            payload["blocks"] = blocks
        resp = requests.post(url, json=payload, timeout=10)
        return resp.status_code == 200
    except Exception as e:
        print(f"Slack error: {e}")
        return False


def slack_new_submission(submission: dict, submitter_name: str) -> bool:
    risk_emoji = {"high": "🔴", "medium": "🟡", "low": "🟠", "pass": "🟢"}.get(
        submission.get("overall_risk", ""), "⚪"
    )
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": "📋 New Compliance Review Required"}},
        {"type": "section", "fields": [
            {"type": "mrkdwn", "text": f"*Document:*\n{submission.get('title','')}"},
            {"type": "mrkdwn", "text": f"*Submitted by:*\n{submitter_name}"},
            {"type": "mrkdwn", "text": f"*Risk:*\n{risk_emoji} {submission.get('overall_risk','').upper()}"},
            {"type": "mrkdwn", "text": f"*Priority:*\n{submission.get('priority','normal').upper()}"},
        ]},
        {"type": "actions", "elements": [
            {"type": "button", "text": {"type": "plain_text", "text": "Review Now"},
             "url": f"{APP_URL}?page=review&id={submission.get('id','')}",
             "style": "primary"}
        ]},
    ]
    return send_slack(f"New submission: {submission.get('title','')}", blocks=blocks)


def slack_review_decision(submission: dict, decision: str, reviewer_name: str, notes: str) -> bool:
    icons = {"approved": "✅", "rejected": "❌", "escalated": "⚠️", "in_review": "👀"}
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": f"{icons.get(decision,'📋')} Review Decision: {decision.upper()}"}},
        {"type": "section", "fields": [
            {"type": "mrkdwn", "text": f"*Document:*\n{submission.get('title','')}"},
            {"type": "mrkdwn", "text": f"*Reviewer:*\n{reviewer_name}"},
        ]},
    ]
    if notes:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*Notes:* {notes}"}})
    return send_slack(f"Review decision: {submission.get('title','')} → {decision}", blocks=blocks)


def slack_reg_change(regulation: str, source_name: str, url: str) -> bool:
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": "⚠️ Regulatory Change Detected"}},
        {"type": "section", "text": {"type": "mrkdwn",
            "text": f"*{regulation.upper()}* — Changes detected on *{source_name}*.\nReview your approved materials for compliance impact."}},
        {"type": "actions", "elements": [
            {"type": "button", "text": {"type": "plain_text", "text": "View Source"},
             "url": url},
            {"type": "button", "text": {"type": "plain_text", "text": "Run Impact Check"},
             "url": f"{APP_URL}?page=monitor",
             "style": "danger"}
        ]},
    ]
    return send_slack(f"Regulatory change: {source_name}", blocks=blocks)


def slack_high_risk(submission: dict, finding_count: int, conflict_count: int) -> bool:
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": "🔴 High-Risk Submission Requires Immediate Review"}},
        {"type": "section", "fields": [
            {"type": "mrkdwn", "text": f"*Document:*\n{submission.get('title','')}"},
            {"type": "mrkdwn", "text": f"*High-risk findings:*\n{finding_count}"},
            {"type": "mrkdwn", "text": f"*Prior comm conflicts:*\n{conflict_count}"},
            {"type": "mrkdwn", "text": f"*Product:*\n{submission.get('product','general')}"},
        ]},
        {"type": "actions", "elements": [
            {"type": "button", "text": {"type": "plain_text", "text": "Review Immediately"},
             "url": f"{APP_URL}?page=review&id={submission.get('id','')}",
             "style": "danger"}
        ]},
    ]
    return send_slack(f"HIGH RISK: {submission.get('title','')}", blocks=blocks)


# ── Email ──────────────────────────────────────────────────────────────────────

def _send_email(to_email: str, subject: str, html_body: str) -> bool:
    smtp_host = os.environ.get("SMTP_HOST")
    smtp_port = int(os.environ.get("SMTP_PORT", 587))
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASSWORD")
    from_email = os.environ.get("FROM_EMAIL", smtp_user or "compliance@company.com")

    if not smtp_host or not smtp_user:
        print(f"Email skipped (SMTP not configured) — would send to {to_email}: {subject}")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_email
        msg["To"] = to_email
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(from_email, to_email, msg.as_string())
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False


def _email_template(title: str, body: str, cta_text: str = "", cta_url: str = "") -> str:
    cta = f'<a href="{cta_url}" style="display:inline-block;padding:10px 20px;background:#1C2D4F;color:white;text-decoration:none;border-radius:6px;margin-top:16px;">{cta_text}</a>' if cta_text else ""
    return f"""
    <html><body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;color:#333;">
    <div style="background:#1C2D4F;padding:20px 24px;border-radius:8px 8px 0 0;">
        <h1 style="color:white;margin:0;font-size:20px;">⚖️ Compliance Checker</h1>
    </div>
    <div style="background:#f9f9f9;padding:24px;border:1px solid #e0e0e0;border-radius:0 0 8px 8px;">
        <h2 style="color:#1C2D4F;margin-top:0;">{title}</h2>
        {body}
        {cta}
    </div>
    <p style="color:#999;font-size:12px;text-align:center;margin-top:16px;">
        Credit Card Compliance Checker · Automated notification
    </p>
    </body></html>
    """


def email_submission_received(user_email: str, user_name: str, submission_title: str, submission_id: str) -> bool:
    body = f"<p>Hi {user_name},</p><p>Your document <strong>{submission_title}</strong> has been submitted for compliance review. You'll receive a notification when a decision is made.</p>"
    html = _email_template("Submission Received", body, "View Submission", f"{APP_URL}?page=my_submissions&id={submission_id}")
    return _send_email(user_email, f"Compliance Review: {submission_title}", html)


def email_review_decision(user_email: str, user_name: str, submission_title: str,
                           decision: str, notes: str, submission_id: str) -> bool:
    icons = {"approved": "✅ Approved", "rejected": "❌ Rejected",
             "escalated": "⚠️ Escalated", "in_review": "👀 In Review"}
    decision_label = icons.get(decision, decision.upper())
    color = {"approved": "#2E7D32", "rejected": "#C00000",
             "escalated": "#BF8F00", "in_review": "#1565C0"}.get(decision, "#333")
    body = f"""
    <p>Hi {user_name},</p>
    <p>A review decision has been made for <strong>{submission_title}</strong>:</p>
    <p style="font-size:18px;font-weight:bold;color:{color};">{decision_label}</p>
    {"<p><strong>Reviewer notes:</strong> " + notes + "</p>" if notes else ""}
    """
    html = _email_template(f"Review Decision: {decision.upper()}", body, "View Details", f"{APP_URL}?page=my_submissions&id={submission_id}")
    return _send_email(user_email, f"Compliance Decision: {submission_title} — {decision.upper()}", html)


def email_reg_change(user_email: str, user_name: str, regulation: str, source_name: str, url: str) -> bool:
    body = f"""
    <p>Hi {user_name},</p>
    <p>A change has been detected on <strong>{source_name}</strong> ({regulation.upper()}).</p>
    <p>Please review your approved marketing materials and policies to ensure they remain compliant with the updated guidance.</p>
    """
    html = _email_template(f"⚠️ Regulatory Change: {regulation.upper()}", body, "View Change", url)
    return _send_email(user_email, f"Regulatory Change Detected: {regulation.upper()}", html)


# ── Unified dispatcher ─────────────────────────────────────────────────────────

def dispatch(event_type: str, **kwargs) -> dict:
    """
    Send both Slack and email for an event.
    Returns {"slack": bool, "email": bool}
    """
    results = {"slack": False, "email": False}

    if event_type == "new_submission":
        results["slack"] = slack_new_submission(kwargs.get("submission",{}), kwargs.get("submitter_name",""))
        if kwargs.get("reviewer_email"):
            results["email"] = email_submission_received(
                kwargs["reviewer_email"], kwargs.get("reviewer_name","Reviewer"),
                kwargs.get("submission",{}).get("title",""), kwargs.get("submission",{}).get("id","")
            )

    elif event_type == "review_decision":
        results["slack"] = slack_review_decision(
            kwargs.get("submission",{}), kwargs.get("decision",""),
            kwargs.get("reviewer_name",""), kwargs.get("notes","")
        )
        if kwargs.get("submitter_email"):
            results["email"] = email_review_decision(
                kwargs["submitter_email"], kwargs.get("submitter_name",""),
                kwargs.get("submission",{}).get("title",""),
                kwargs.get("decision",""), kwargs.get("notes",""),
                kwargs.get("submission",{}).get("id","")
            )

    elif event_type == "reg_change":
        results["slack"] = slack_reg_change(
            kwargs.get("regulation",""), kwargs.get("source_name",""), kwargs.get("url","")
        )
        if kwargs.get("user_emails"):
            for email, name in kwargs["user_emails"]:
                email_reg_change(email, name, kwargs.get("regulation",""),
                                 kwargs.get("source_name",""), kwargs.get("url",""))
            results["email"] = True

    elif event_type == "high_risk":
        results["slack"] = slack_high_risk(
            kwargs.get("submission",{}),
            kwargs.get("finding_count", 0),
            kwargs.get("conflict_count", 0)
        )

    return results
