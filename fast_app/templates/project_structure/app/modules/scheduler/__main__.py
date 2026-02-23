import asyncio

import fast_app.boot  # noqa: F401
from fast_app.core.scheduler import run_scheduler

if __name__ == "__main__":
    asyncio.run(
        run_scheduler(
            [
                # Add your scheduled jobs here
                # Interval in seconds:
                # {"run_every_s": 60 * 60 * 24, "function": Auth.cleanup_expired}
                # Human-readable interval:
                # {"run_every": "5m", "function": fast_app.integrations.log_watcher.log_watcher_slack.send_log_errors_via_slack}
                # Cron (minute hour day month weekday), timezone defaults to UTC:
                # {"cron": "0 0 * * *", "function": Auth.cleanup_expired}
                # Cron with timezone:
                # {"cron": "0 0 * * sat,sun", "timezone": "Europe/Prague", "function": Auth.cleanup_expired}
                # Optional: provide custom "identifier"; otherwise derived from function
            ]
        )
    )
