import os
import json
from datetime import datetime
from pathlib import Path

class VequilNotifier:
    """Enterprise notification engine for Vequil Agentic Recon Engine."""

    def __init__(self):
        self.slack_webhook = os.getenv("SLACK_WEBHOOK_URL")
        self.admin_email = os.getenv("ADMIN_EMAIL", "admin@vequil.com")
        self.logs_dir = Path(__file__).resolve().parents[2] / "data" / "logs"
        self.logs_dir.mkdir(exist_ok=True, parents=True)
        self.email_log = self.logs_dir / "outbound_emails.log"

    def notify_lead(self, email: str) -> None:
        """Send notification of a new demo request."""
        subject = f"New Lead: {email}"
        body = f"A new demo request has been received from {email} at {datetime.now().isoformat()}."
        print(f"   [NOTIFIER] Sending Lead Alert: {email}")
        self._send_email(self.admin_email, subject, body)
        self._send_slack(f"🚀 *New Lead:* {email}")

    def notify_variance_alert(self, event_id: str, amount: float, count: int) -> None:
        """Trigger a high-priority financial variance alert."""
        threshold = 500.0  # Alert if variance > $500
        if abs(amount) < threshold:
            return

        subject = f"CRITICAL: High Variance Detected - {event_id or 'Latest'}"
        body = (
            f"Vequil Recon Engine has detected a significant financial variance.\n\n"
            f"• Event ID: {event_id or 'Current'}\n"
            f"• Net Variance: ${amount:,.2f}\n"
            f"• Finding Count: {count}\n\n"
            f"Please review the Exception Queue immediately: http://localhost:8000/dashboard.html"
        )
        print(f"   [NOTIFIER] Sending Variance Alert: {event_id} (${amount:,.2f})")
        self._send_email(self.admin_email, subject, body)
        self._send_slack(f"🚨 *CRITICAL:* High Variance in `{event_id or 'Latest'}`: *${amount:,.2f}*")

    def _send_email(self, to: str, subject: str, body: str) -> None:
        """Send an email (Mocked to log file for production readiness)."""
        entry = {
            "to": to,
            "subject": subject,
            "body": body,
            "timestamp": datetime.now().isoformat()
        }
        with open(self.email_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    def _send_slack(self, text: str) -> None:
        """Send a Slack message if a webhook is configured."""
        if not self.slack_webhook:
            return

        try:
            import requests
            requests.post(self.slack_webhook, json={"text": text}, timeout=5)
        except Exception as e:
            print(f"   [NOTIFIER] Slack delivery failed: {e}")

# Global instance
notifier = VequilNotifier()
