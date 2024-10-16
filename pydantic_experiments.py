from datetime import datetime, date
from typing import List

from pydantic import BaseModel


class GoogleCalendarEvent(BaseModel):
    id: str  # may contain _ as illegal character
    # status: str  # only "confirmed" events are returned
    summary: str
    description: str
    location: str
    attendees: str  # separated by comma (or ", "), usually no comma if there is only 1 attendee
    start: datetime | date  # date for all-day events, otherwise Google uses e.g. 2024-01-05T19:15:00+00:00
    end: datetime | date


class OutlookCalendarEvent(BaseModel):
    iCalUId: str
    subject: str
    body: str
    startWithTimeZone: datetime  # 2017-08-29T04:00:00.0000000+00:00 or 2024-09-09T07:15:00+00:00
    endWithTimeZone: datetime
    requiredAttendees: str  # separated by semicolon, also if there is only 1 attendee (e.g. "foo@bar;")
    responseType: str


class CalendarEventList(BaseModel):
    events: List[GoogleCalendarEvent | OutlookCalendarEvent]


input_data = [
    {
        "y": "Event 1",
        "x": "y"
    },
    {
        "title": "Event 2"
    }
]
