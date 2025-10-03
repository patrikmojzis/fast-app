import asyncio

import fast_app.boot
from fast_app.core.scheduler import run_scheduler

if __name__ == "__main__":
    asyncio.run(run_scheduler([
        # Add your scheduled jobs here
        # Example:
        # {"run_every_s": 60 * 60 * 24, "function": Auth.cleanup_expired}
        # {"run_every_s": 60 * 5, "function": fast_app.integrations.log_watcher.log_watcher_slack.send_log_errors_via_slack}
        # Optional: provide custom "identifier"; otherwise derived from function
    ]))


