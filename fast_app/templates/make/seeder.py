import asyncio

from app.app_provider import boot


async def _seed():
    # Implement your async seeding logic here
    pass


def seed() -> None:
    boot()
    asyncio.run(_seed())


if __name__ == '__main__':
    seed()


