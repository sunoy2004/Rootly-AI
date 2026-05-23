import logging
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional


logger = logging.getLogger(__name__)


SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
ALERT_EMAIL_TO = os.getenv("ALERT_EMAIL_TO", "")


class EmailAlerter:
    def __init__(self):
        self.host = SMTP_HOST
        self.port = SMTP_PORT
        self.username = SMTP_USERNAME
        self.password = SMTP_PASSWORD
        self.to_email = ALERT_EMAIL_TO

    async def send(self, incident: dict, ai_analysis: Optional[dict] = None):
        if not self.username or not self.password or not self.to_email:
            logger.warning("Email credentials not configured, skipping email alert")
            return

        subject = f"[{incident.get('severity', 'WARNING')}] {incident.get('title', 'Incident Alert')}"

        body_lines = [
            f"Incident ID: {incident.get('id', 'unknown')}",
            f"Service: {incident.get('affected_services', ['unknown'])[0]}",
            f"Severity: {incident.get('severity', 'WARNING')}",
            f"Source: {incident.get('source', 'unknown')}",
            f"Status: {incident.get('status', 'OPEN')}",
            "",
            f"Title: {incident.get('title', 'N/A')}",
            "",
        ]

        if incident.get("root_cause"):
            body_lines.append(f"Root Cause: {incident['root_cause']}")
            body_lines.append(f"Confidence: {int((incident.get('confidence', 0) or 0) * 100)}%")
            body_lines.append("")

        if ai_analysis:
            body_lines.append("AI Analysis:")
            body_lines.append(f"  Probable Cause: {ai_analysis.get('probable_cause', 'N/A')}")
            body_lines.append(f"  Explanation: {ai_analysis.get('detailed_explanation', 'N/A')}")
            if ai_analysis.get("debug_steps"):
                body_lines.append("  Debug Steps:")
                for i, step in enumerate(ai_analysis.get("debug_steps", [])[:5], 1):
                    body_lines.append(f"    {i}. {step}")
            body_lines.append("")

        body_lines.append("View in Dashboard: http://localhost:3000")
        body_lines.append("View Traces: http://localhost:16686")

        body = "\n".join(body_lines)

        msg = MIMEMultipart()
        msg["From"] = self.username
        msg["To"] = self.to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        try:
            server = smtplib.SMTP(self.host, self.port)
            server.starttls()
            server.login(self.username, self.password)
            server.sendmail(self.username, self.to_email, msg.as_string())
            server.quit()
            logger.info(f"Email alert sent for incident {incident.get('id')}")
        except Exception as e:
            logger.error(f"Email alert failed: {e}")
