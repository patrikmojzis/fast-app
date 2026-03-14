import argparse

from fast_app.cli.publish_command import PublishCommand


def test_publish_command_rejects_traversal_package(monkeypatch, capsys) -> None:
    command = PublishCommand()

    def _unexpected_copy(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("copy_tree should not run for invalid package names")

    monkeypatch.setattr("fast_app.cli.publish_command.copy_tree", _unexpected_copy)

    command.execute(argparse.Namespace(package="../socketio"))

    captured = capsys.readouterr().out
    assert "Package '../socketio' not found" in captured
