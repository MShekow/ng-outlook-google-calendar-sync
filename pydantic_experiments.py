from datetime import datetime, date
from typing import List

from pydantic import BaseModel


class GoogleCalendarEvent(BaseModel, validate_assignment=True):
    start: datetime

foo = GoogleCalendarEvent(start="2024-09-09T07:00:00+00:00")

foo.start = "2024-09-10T07:00:00+00:00"
i = 2
