from fast_app.app_provider import boot
boot()

from fast_app.core.cron import run_cron
import asyncio

if __name__ == "__main__":
    asyncio.run(run_cron([
        # Add your cron jobs here
        # Example:
        # {"run_every_s": 10, "function": lambda: print("test")}
        # Optional: provide custom "identifier"; otherwise derived from function
    ]))
