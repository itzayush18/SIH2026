"""Notification dispatch- Slack webhook (implemented) + SMTP email (stub).

Both are opt-in via environment variables. If a channel is not configured, the
dispatcher records a `queued` event but does not attempt to send- never fail
loudly for missing optional credentials.
"""
from __future__ import annotations

import json
import os
import smtplib
import urllib.request
from email.message import EmailMessage


def _post_json(url, body, timeout=6.0):
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status


def dispatch(alert, incident_summary):
    """Fan an alert out to every configured channel. Returns a list of
    per-channel results so the caller can log or expose them."""
    out = []
    slack = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
    if slack:
        text = (f"*[{alert['severity']}] {alert['title']}*\n"
                f"{alert['message']}\n"
                f"Incident *{incident_summary['incident_id']}* · "
                f"{incident_summary['scenario']['subtitle']}")
        try:
            out.append(("slack", "sent", _post_json(slack, {"text": text})))
        except Exception as e:
            out.append(("slack", "error", str(e)))
    else:
        out.append(("slack", "not_configured", None))

    to = os.environ.get("ALERT_EMAIL_TO", "").strip()
    host = os.environ.get("SMTP_HOST", "").strip()
    if to and host:
        try:
            msg = EmailMessage()
            msg["Subject"] = f"[OILTRACE {alert['severity']}] {alert['title']}"
            msg["From"] = os.environ.get("SMTP_FROM", "oiltrace@localhost")
            msg["To"] = to
            msg.set_content(f"{alert['message']}\n\nIncident: "
                            f"{incident_summary['incident_id']}\n"
                            f"{incident_summary['scenario']['subtitle']}")
            port = int(os.environ.get("SMTP_PORT", "587"))
            with smtplib.SMTP(host, port, timeout=8) as s:
                if os.environ.get("SMTP_USER"):
                    s.starttls()
                    s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
                s.send_message(msg)
            out.append(("email", "sent", None))
        except Exception as e:
            out.append(("email", "error", str(e)))
    else:
        out.append(("email", "not_configured", None))
    return out


def dispatch_critical(rep):
    """Send only CRITICAL/HIGH alerts- the interesting subset by default."""
    from . import incidents as _inc
    summ = _inc.summary(rep)
    results = []
    for a in rep["oiltrace"]["alerts"]:
        if a["severity"] in ("CRITICAL", "HIGH"):
            results.append({"alert_id": a["id"], "channels": dispatch(a, summ)})
    return results
