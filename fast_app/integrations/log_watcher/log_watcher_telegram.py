import os
from typing import List

from fast_app.exceptions.common_exceptions import EnvMissingException
from fast_app.integrations.notification_channels.telegram import send_via_telegram
from fast_app.utils.log_errors_checker import (
    LogErrorsChecker,
    LogErrorEntry,
    DEFAULT_LOG_ERRORS_CHECK_MINUTES,
    process_traceback,
)


def _escape_markdown(text: str) -> str:
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text


def _format_error_for_telegram(error: LogErrorEntry) -> str:
    formatted = f"*\\[{_escape_markdown(error['level'])}\\]* {_escape_markdown(error['timestamp'])}\n"
    formatted += f"*Logger:* {_escape_markdown(error['logger'])}\n"
    formatted += f"*Message:* {_escape_markdown(error['message'])}\n"

    if error['traceback']:
        traceback_lines = process_traceback(error['traceback'])
        traceback_text = '\n'.join(traceback_lines)
        formatted += f"\n*Traceback:*\n```\n{traceback_text}\n```"

    return formatted + "\n"


async def send_log_errors_via_telegram() -> None:
    bot_token = os.getenv('SEND_LOG_ERRORS_TELEGRAM_BOT_TOKEN')
    if not bot_token:
        raise EnvMissingException('SEND_LOG_ERRORS_TELEGRAM_BOT_TOKEN')

    chat_id = os.getenv('SEND_LOG_ERRORS_TELEGRAM_CHAT_ID')
    if not chat_id:
        raise EnvMissingException('SEND_LOG_ERRORS_TELEGRAM_CHAT_ID')

    env = os.getenv('ENV', 'unknown')
    check_minutes = DEFAULT_LOG_ERRORS_CHECK_MINUTES

    checker = LogErrorsChecker(check_minutes=check_minutes)
    errors = checker.get_error_entries()
    if not errors:
        return

    message = f"🚨 *ERROR Alert: salespanda\\-app*\n"
    message += f"*Environment:* {_escape_markdown(env.upper())}\n"
    message += f"*Found {len(errors)} error\\(s\\) in the last {check_minutes} minutes*\n\n"

    for i, error in enumerate(errors):
        if len(message) > 3500:
            remaining = len(errors) - i
            message += f"\\.\\.\\. and {remaining} more error\\(s\\) \\(" \
                       f"truncated to fit Telegram limits\\)"
            break

        formatted_error = _format_error_for_telegram(error)
        message += formatted_error

        if i < len(errors) - 1:
            message += "\n" + "\\-" * 20 + "\n\n"

    await send_via_telegram(message, bot_token, chat_id)


