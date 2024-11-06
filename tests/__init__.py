from pydantic import TypeAdapter

from calendar_sync_helper.entities.entities_v1 import AbstractCalendarEvent

type_adapter = TypeAdapter(list[AbstractCalendarEvent])


def parse_abstract_calendar_event_list(json_list: list[dict]) -> list[AbstractCalendarEvent]:
    return type_adapter.validate_python(json_list)

def fix_file_location_for_localhost(localhost_file_location: str) -> str:
    """
    Replaces URLs such as "https://locahost:12345/..." with a more complex host, because the sync service handlers
    call "validators.url()" which rejects "localhost" by default,
    see https://github.com/python-validators/validators/issues/392
    """
    return localhost_file_location.replace("localhost", "127.0.0.1.nip.io")
