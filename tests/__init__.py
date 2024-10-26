from pydantic import TypeAdapter

from calendar_sync_helper.entities.entities_v1 import AbstractCalendarEvent

type_adapter = TypeAdapter(list[AbstractCalendarEvent])


def parse_abstract_calendar_event_list(json_list: list[dict]) -> list[AbstractCalendarEvent]:
    return type_adapter.validate_python(json_list)
