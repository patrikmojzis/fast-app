from pydantic import BaseModel

from fast_app.utils.serialisation import pascal_case_to_snake_case, remove_suffix


class Event(BaseModel):
    """
    Base class for all events in the application.
    Events are data containers that describe something that happened.
    """
    model_config = {"arbitrary_types_allowed": True}
    
    def get_event_name(self) -> str:
        """Get the event type for identification purposes."""
        name = pascal_case_to_snake_case(self.__class__.__name__)
        return remove_suffix(name, "_event")