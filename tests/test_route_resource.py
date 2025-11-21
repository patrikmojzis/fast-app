from __future__ import annotations

import pytest

from fast_app import Route


class LeadController:
    def index(self) -> str:
        return "index"

    def show(self) -> str:
        return "show"

    def store(self) -> str:
        return "store"

    def destroy(self) -> str:
        return "destroy"

    def update(self) -> str:
        return "update"


def test_resource_generates_default_crud_routes() -> None:
    controller = LeadController()

    resource_group = Route.resource("/lead", controller)

    flattened = resource_group.flatten()

    assert [route.methods for route in flattened] == [
        ["GET"],
        ["GET"],
        ["POST"],
        ["DELETE"],
        ["PATCH"],
    ]
    assert [route.path for route in flattened] == [
        "/lead",
        "/lead/<lead_id>",
        "/lead",
        "/lead/<lead_id>",
        "/lead/<lead_id>",
    ]

    handlers = [
        controller.index,
        controller.show,
        controller.store,
        controller.destroy,
        controller.update,
    ]
    assert [route.handler for route in flattened] == handlers
    assert all(route.middlewares is None for route in flattened)


class ProfileController:
    def list(self) -> str:
        return "list"

    def retrieve(self) -> str:
        return "retrieve"

    def create(self) -> str:
        return "create"

    def destroy(self) -> str:
        return "destroy"

    def modify(self) -> str:
        return "modify"


def test_resource_supports_overrides_and_parameter_naming() -> None:
    controller = ProfileController()

    def middleware_factory(handler):  # pragma: no cover - behaviour not executed
        return handler

    resource_group = Route.resource(
        "/user-profiles",
        controller,
        middlewares=[middleware_factory],
        controller_methods={
            "index": "list",
            "show": "retrieve",
            "store": "create",
            "update": "modify",
        },
        parameter="profile_uuid",
    )

    flattened = resource_group.flatten()
    assert resource_group.middlewares == [middleware_factory]

    assert [route.path for route in flattened] == [
        "/user-profiles",
        "/user-profiles/<profile_uuid>",
        "/user-profiles",
        "/user-profiles/<profile_uuid>",
        "/user-profiles/<profile_uuid>",
    ]
    assert all(route.middlewares == [middleware_factory] for route in flattened)

    handlers = [
        controller.list,
        controller.retrieve,
        controller.create,
        controller.destroy,
        controller.modify,
    ]
    assert [route.handler for route in flattened] == handlers


class IncompleteController:
    def index(self) -> str:  # pragma: no cover - invoked indirectly
        return "index"


def test_resource_requires_all_actions() -> None:
    controller = IncompleteController()

    with pytest.raises(AttributeError, match="'show' for resource action"):
        Route.resource("/lead", controller)

