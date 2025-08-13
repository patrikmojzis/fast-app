from fast_app.app_provider import boot
boot()

from fast_app.core.cron import run_cron
import asyncio

if __name__ == "__main__":
    asyncio.run(run_cron([
        # Add your cron jobs here
        # Example:
        # {"run_every_s": 60 * 60 * 24, "function": Auth.cleanup_expired}
        # {"run_every_s": 60 * 5, "function": fast_app.integrations.log_watcher.log_watcher_slack.send_log_errors_via_slack}
        # Optional: provide custom "identifier"; otherwise derived from function
    ]))
