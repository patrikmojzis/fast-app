import argparse
from pathlib import Path
from textwrap import dedent

from fast_app.cli.migrate_command import MigrateCommand


def test_migrate_resolves_single_local_contract_subclass_for_snake_case_name(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    migration_path = Path("app/db/migrations/lead_note_refactor.py")
    migration_path.parent.mkdir(parents=True)
    migration_path.write_text(
        dedent(
            """
            from fast_app.contracts.migration import Migration


            class LeadNoteRefactor(Migration):
                async def migrate(self) -> None:
                    pass
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    executed: dict[str, str] = {}
    command = MigrateCommand()
    monkeypatch.setattr(
        command,
        "_run_contract",
        lambda contract, migration_name: executed.update(
            {"contract_class": contract.__class__.__name__, "migration_name": migration_name}
        ),
    )

    command.execute(argparse.Namespace(name="lead_note_refactor", path=None))

    assert executed == {
        "contract_class": "LeadNoteRefactor",
        "migration_name": "lead_note_refactor",
    }


def test_migrate_reports_ambiguous_local_contract_subclasses(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    migration_path = Path("app/db/migrations/lead_note_refactor.py")
    migration_path.parent.mkdir(parents=True)
    migration_path.write_text(
        dedent(
            """
            from fast_app.contracts.migration import Migration


            class LeadNoteRefactor(Migration):
                async def migrate(self) -> None:
                    pass


            class LeadNoteCleanup(Migration):
                async def migrate(self) -> None:
                    pass
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    command = MigrateCommand()
    command.execute(argparse.Namespace(name="lead_note_refactor", path=None))

    output = capsys.readouterr().out
    assert "Multiple migration classes found in the module" in output
    assert "LeadNoteCleanup" in output
    assert "LeadNoteRefactor" in output
