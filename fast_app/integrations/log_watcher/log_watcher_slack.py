import os
from typing import List

from fast_app.exceptions.common_exceptions import EnvMissingException
from fast_app.common.notification_channels.slack import send_via_slack
from fast_app.utils.log_errors_checker import (
    LogErrorsChecker,
    LogErrorEntry,
    DEFAULT_LOG_ERRORS_CHECK_MINUTES,
    process_traceback,
)


def _format_slack_blocks(env: str, check_minutes: int, errors: List[LogErrorEntry]) -> list[dict]:
    error_count = len(errors)

    blocks: list[dict] = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"🚨 *ERROR Alert: salespanda-app*\n*Environment: {env.upper()}*\n*Found {error_count} error(s) in the last {check_minutes} minutes*",
            },
        }
    ]

    for i, error in enumerate(errors):
        if len(str(blocks)) > 35000:
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"... and {error_count - i} more errors (truncated to fit Slack limits)",
                    },
                }
            )
            break

        error_text = f"*[{error['level']}] * {error['timestamp']}\n"
        error_text += f"*Logger:* {error['logger']}\n"
        error_text += f"*Message:* {error['message']}\n"

        if error['traceback']:
            traceback_lines = process_traceback(error['traceback'])
            traceback_text = "\n".join(traceback_lines)
            error_text += f"\n*Traceback:*\n```\n{traceback_text}\n```"

        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": error_text}})
        if i < len(errors) - 1:
            blocks.append({"type": "divider"})

    return blocks


async def send_log_errors_via_slack() -> None:
    webhook_url = os.getenv("SEND_LOG_ERRORS_SLACK_WEBHOOK_URL")
    if not webhook_url:
        raise EnvMissingException("SEND_LOG_ERRORS_SLACK_WEBHOOK_URL")

    env = os.getenv("ENV", "unknown")
    check_minutes = DEFAULT_LOG_ERRORS_CHECK_MINUTES

    checker = LogErrorsChecker(check_minutes=check_minutes)
    errors = checker.get_error_entries()
    if not errors:
        return

    blocks = _format_slack_blocks(env, check_minutes, errors)
    payload = {
        "text": f"🚨 salespanda-app ERROR Alert ({env.upper()}): Found {len(errors)} error(s)",
        "blocks": blocks,
    }
    await send_via_slack(payload, webhook_url)


