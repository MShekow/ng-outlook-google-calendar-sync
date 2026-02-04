from datetime import datetime, date, time, UTC
from typing import Self, Optional

from pydantic import BaseModel


class GoogleCalendarEvent(BaseModel):
    id: str  # may contain _ as illegal character
    # status: str  # only "confirmed" events are returned
    summary: str
    description: str
    location: str
    attendees: str  # separated by comma (or ", "), usually no comma if there is only 1 attendee
    start: date | datetime  # date for all-day events, otherwise Google uses e.g. 2024-01-05T19:15:00+00:00
    end: date | datetime


class OutlookCalendarEvent(BaseModel):
    id: str
    subject: str
    body: str
    location: str
    startWithTimeZone: datetime  # 2017-08-29T04:00:00.0000000+00:00 or 2024-09-09T07:15:00+00:00
    endWithTimeZone: datetime
    requiredAttendees: str  # separated by semicolon, also if there is only 1 attendee (e.g. "foo@bar;")
    responseType: str
    isAllDay: bool
    showAs: str
    sensitivity: str


class AbstractCalendarEvent(BaseModel):
    sync_correlation_id: str
    title: str
    description: str
    location: str
    start: datetime
    end: datetime
    is_all_day: bool
    attendees: Optional[str] = None  # only filled by "compute-actions" endpoint, to insert the corresponding event's ID
    show_as: Optional[str] = None  # Outlook only
    sensitivity: Optional[str] = None  # Outlook only

    @classmethod
    def from_implementation(cls, event_impl: GoogleCalendarEvent | OutlookCalendarEvent,
                            anonymize_fields: bool = False) -> Self:
        if isinstance(event_impl, GoogleCalendarEvent):
            # Normalize start and end to consistent types - Google Calendar API can sometimes return
            # mixed types (date for start, datetime at midnight for end) for events ending exactly at midnight
            start_val = event_impl.start
            end_val = event_impl.end

            # Handle case where end is a datetime at midnight but start is a date
            if type(start_val) == date and type(end_val) == datetime:
                if end_val.hour == 0 and end_val.minute == 0 and end_val.second == 0:
                    # Convert midnight datetime to date for consistency
                    end_val = end_val.date()
                else:
                    raise ValueError(f"For event titled '{event_impl.summary}', the start is a date (not datetime), "
                                     f"but the end is a datetime with non-midnight time ({end_val.time()}), "
                                     f"which is inconsistent")

            # Handle case where start is a datetime but end is a date
            if type(start_val) == datetime and type(end_val) == date:
                if start_val.hour == 0 and start_val.minute == 0 and start_val.second == 0:
                    # Start is at midnight - treat as all-day event, convert start to date
                    start_val = start_val.date()
                else:
                    # Timed event ending at midnight - Google returns end as date instead of datetime
                    # Convert the end date to a datetime at midnight (00:00:00 UTC)
                    zero_am_utc = time(hour=0, minute=0, second=0, tzinfo=UTC)
                    end_val = datetime.combine(end_val, zero_am_utc)

            if type(start_val) == date:
                # all-day event, where e.g. start="2024-10-01" and end="2024-10-02" indicates a ONE-day-long event,
                # that is, the interval notation would be: [start, end)

                # Convert the start/end date object to datetime objects
                zero_am_utc = time(hour=0, minute=0, second=0, tzinfo=UTC)
                start_time = datetime.combine(start_val, zero_am_utc)
                if not type(end_val) == date:
                    raise ValueError(f"For event titled '{event_impl.summary}', the start is a date (not datetime), "
                                     f"but the end is a datetime, which makes no sense")
                date_diff = end_val - start_val
                if date_diff.days == 0:
                    raise ValueError(f"For event titled '{event_impl.summary}', the start and end date is the same,"
                                     f"'{start_val}', but expected it to be at least one day apart")

                end_time = datetime.combine(end_val, zero_am_utc)
                is_all_day = True
            else:
                start_time = start_val
                end_time = end_val
                is_all_day = False

            return cls(
                sync_correlation_id=event_impl.id,
                title="" if anonymize_fields else event_impl.summary,
                description="" if anonymize_fields else event_impl.description,
                location="" if anonymize_fields else event_impl.location,
                start=start_time,
                end=end_time,
                is_all_day=is_all_day
            )

        return cls(
            sync_correlation_id=event_impl.id,
            title="" if anonymize_fields else event_impl.subject,
            description="" if anonymize_fields else event_impl.body,
            location="" if anonymize_fields else event_impl.location,
            start=event_impl.startWithTimeZone,
            end=event_impl.endWithTimeZone,
            is_all_day=event_impl.isAllDay,
            show_as=event_impl.showAs,
            sensitivity=event_impl.sensitivity
        )


type ImplSpecificEvent = GoogleCalendarEvent | OutlookCalendarEvent


class CalendarEventList(BaseModel):
    events: list[ImplSpecificEvent]


class ComputeActionsInput(BaseModel):
    cal1events: list[ImplSpecificEvent]
    cal2events: list[AbstractCalendarEvent]


class ComputeActionsResponse(BaseModel):
    events_to_delete: list[AbstractCalendarEvent]
    events_to_update: list[AbstractCalendarEvent]
    events_to_create: list[AbstractCalendarEvent]
