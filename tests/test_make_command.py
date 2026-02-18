import argparse
from pathlib import Path

from fast_app.cli.make_command import MakeCommand


def test_make_controller_from_snake_case_name(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    command = MakeCommand()
    args = argparse.Namespace(type="controller", name="property_controller", path=None)

    command.execute(args)

    generated = Path("app/http_files/controllers/property_controller.py")
    assert generated.exists()

    content = generated.read_text(encoding="utf-8")
    assert "from app.models.property import Property" in content
    assert "from app.http_files.schemas.property_schema import PropertySchema, PropertyPartialSchema" in content
    assert "from app.http_files.resources.property_resource import PropertyResource" in content
    assert "async def show(property: Property):" in content
    assert "async def update(property: Property, data: PropertyPartialSchema):" in content


def test_make_controller_from_pascal_case_name(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    command = MakeCommand()
    args = argparse.Namespace(type="controller", name="PropertyController", path=None)

    command.execute(args)

    generated = Path("app/http_files/controllers/property_controller.py")
    assert generated.exists()

    content = generated.read_text(encoding="utf-8")
    assert "from app.models.property import Property" in content
    assert "async def store(data: PropertySchema):" in content
    assert "property = await Property.create(data.validated)" in content
