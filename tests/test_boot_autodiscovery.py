import sys
import pytest

from fast_app.app_provider import boot
from fast_app.application import Application
from fast_app.core.events import dispatch_now


@pytest.mark.asyncio
async def test_boot_autodiscovery(tmp_path, monkeypatch):
    app_dir = tmp_path / "app"
    models_dir = app_dir / "models"
    observers_dir = app_dir / "observers"
    policies_dir = app_dir / "policies"
    for d in (app_dir, models_dir, observers_dir, policies_dir):
        d.mkdir()

    (models_dir / "user.py").write_text(
        "from fast_app import Model\n"
        "class User(Model):\n"
        "    name: str\n"
    )

    (observers_dir / "user_observer.py").write_text(
        "from fast_app import Observer\n"
        "class UserObserver(Observer):\n"
        "    async def on_creating(self, model):\n"
        "        pass\n"
    )

    (policies_dir / "user_policy.py").write_text(
        "from fast_app import Policy\n"
        "class UserPolicy(Policy):\n"
        "    async def find(self, query):\n"
        "        return query\n"
    )

    (app_dir / "event_provider.py").write_text(
        "from fast_app import Event, EventListener\n"
        "class BootEvent(Event):\n"
        "    pass\n"
        "class BootListener(EventListener):\n"
        "    called = False\n"
        "    async def handle(self):\n"
        "        BootListener.called = True\n"
        "events = {BootEvent: [BootListener]}\n"
    )

    sys.path.insert(0, str(tmp_path))
    monkeypatch.chdir(tmp_path)
    Application().reset()
    try:
        boot()
        from app.models.user import User
        from app.observers.user_observer import UserObserver
        from app.policies.user_policy import UserPolicy
        import app.event_provider as ep

        instance = User(name="A")
        assert any(isinstance(o, UserObserver) for o in instance.observers)
        assert isinstance(User.policy, UserPolicy)

        await dispatch_now(ep.BootEvent())
        assert ep.BootListener.called
    finally:
        sys.path.pop(0)
        for mod in list(sys.modules):
            if mod.startswith("app"):
                sys.modules.pop(mod, None)
        Application().reset()
