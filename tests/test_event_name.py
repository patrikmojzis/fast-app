import pytest

from fast_app import Event


def test_get_event_name_without_event_suffix_keeps_full_name():
    class NewUserMessage(Event):
        pass

    assert NewUserMessage().get_event_name() == "new_user_message"


def test_get_event_name_with_event_suffix_strips_exact_suffix():
    class NewUserRegisteredEvent(Event):
        pass

    assert NewUserRegisteredEvent().get_event_name() == "new_user_registered"


