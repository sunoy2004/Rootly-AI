import logging
from typing import Optional, Dict, Any

import httpx


logger = logging.getLogger(__name__)


class SlackAlerter:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
        self.client = httpx.AsyncClient()

    async def send(
        self,
        incident: dict,
        ai_analysis: Optional[dict] = None,
        is_escalation: bool = False,
    ):
        severity = incident.get("severity", "WARNING")
        service = (
            incident.get("affected_services", [""])[0]
            if incident.get("affected_services")
            else "unknown"
        )
        emoji = "🚨" if severity == "CRITICAL" else "⚠️"
        if is_escalation:
            emoji = "📈"

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} {severity}: {service} incident",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{incident.get('title', 'Unknown incident')}*",
                },
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Service:*\n{service}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Source:*\n{incident.get('source', 'unknown')}",
                    },
                ],
            },
        ]

        if incident.get("root_cause"):
            confidence = incident.get("confidence", 0) or 0
            confidence_pct = int(confidence * 100)
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Root Cause:*\n{incident['root_cause']}\n_Confidence: {confidence_pct}%_",
                    },
                }
            )

        if ai_analysis and ai_analysis.get("debug_steps"):
            steps = "\n".join(
                f"{i + 1}. {s}"
                for i, s in enumerate(ai_analysis["debug_steps"][:5])
            )
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Debug Steps:*\n{steps}",
                    },
                }
            )

        dashboard_url = f"http://localhost:3000/incidents/{incident.get('id', '')}"
        blocks.append(
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "View Dashboard",
                        },
                        "url": dashboard_url,
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "View Traces",
                        },
                        "url": "http://localhost:16686",
                    },
                ],
            }
        )

        try:
            await self.client.post(self.webhook_url, json={"blocks": blocks})
            logger.info(f"Slack alert sent for incident {incident.get('id')}")
        except Exception as e:
            logger.error(f"Slack alert failed: {e}")

    async def close(self):
        await self.client.aclose()
