import argparse
from pathlib import Path
from textwrap import dedent

from fast_app.cli.seed_command import SeedCommand


def test_seed_resolves_single_local_contract_subclass_for_snake_case_name(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    seeder_path = Path("app/db/seeders/load_users.py")
    seeder_path.parent.mkdir(parents=True)
    seeder_path.write_text(
        dedent(
            """
            from fast_app.contracts.seeder import Seeder


            class LoadUsers(Seeder):
                async def seed(self) -> None:
                    pass
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    executed: dict[str, str] = {}
    command = SeedCommand()
    monkeypatch.setattr(
        command,
        "_run_contract",
        lambda contract, seeder_name: executed.update(
            {"contract_class": contract.__class__.__name__, "seeder_name": seeder_name}
        ),
    )

    command.execute(argparse.Namespace(name="load_users", path=None))

    assert executed == {
        "contract_class": "LoadUsers",
        "seeder_name": "load_users",
    }
