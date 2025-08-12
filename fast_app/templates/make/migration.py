import asyncio

from app.app_provider import boot


async def _migrate():
    # Implement your async migration logic here
    pass


def migrate() -> None:
    boot()
    asyncio.run(_migrate())


if __name__ == '__main__':
    migrate()


