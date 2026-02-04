"""
Unit tests for entities_v1.py, specifically testing the from_implementation method
for edge cases like mixed date/datetime types from Google Calendar API.
"""
from datetime import date, datetime, UTC

import pytest

from calendar_sync_helper.entities.entities_v1 import (
    GoogleCalendarEvent,
    AbstractCalendarEvent,
)


class TestGoogleCalendarEventFromImplementation:
    """Tests for AbstractCalendarEvent.from_implementation with GoogleCalendarEvent input."""

    def test_normal_timed_event(self):
        """Test a normal timed event with datetime start and end."""
        event = GoogleCalendarEvent(
            id="test123",
            summary="Meeting",
            description="A meeting",
            location="Office",
            attendees="",
            start=datetime(2024, 2, 2, 14, 0, 0, tzinfo=UTC),
            end=datetime(2024, 2, 2, 15, 0, 0, tzinfo=UTC),
        )
        result = AbstractCalendarEvent.from_implementation(event)
        assert result.is_all_day is False
        assert result.start == datetime(2024, 2, 2, 14, 0, 0, tzinfo=UTC)
        assert result.end == datetime(2024, 2, 2, 15, 0, 0, tzinfo=UTC)

    def test_normal_all_day_event(self):
        """Test a normal all-day event with date start and end."""
        event = GoogleCalendarEvent(
            id="test456",
            summary="Holiday",
            description="All day off",
            location="",
            attendees="",
            start=date(2024, 2, 2),
            end=date(2024, 2, 3),
        )
        result = AbstractCalendarEvent.from_implementation(event)
        assert result.is_all_day is True
        assert result.start == datetime(2024, 2, 2, 0, 0, 0, tzinfo=UTC)
        assert result.end == datetime(2024, 2, 3, 0, 0, 0, tzinfo=UTC)

    def test_date_start_datetime_midnight_end(self):
        """
        Test Google API edge case: start is a date but end is a datetime at midnight.
        This happens when an event ends exactly at midnight - Google may return
        inconsistent types.
        """
        event = GoogleCalendarEvent(
            id="midnight_end_123",
            summary="Lunch with Feng/Kev/Mack",
            description="Event ending at midnight",
            location="Restaurant",
            attendees="",
            start=date(2024, 2, 2),
            end=datetime(2024, 2, 3, 0, 0, 0, tzinfo=UTC),
        )
        result = AbstractCalendarEvent.from_implementation(event)
        # Should be treated as an all-day event
        assert result.is_all_day is True
        assert result.start == datetime(2024, 2, 2, 0, 0, 0, tzinfo=UTC)
        assert result.end == datetime(2024, 2, 3, 0, 0, 0, tzinfo=UTC)
        assert result.title == "Lunch with Feng/Kev/Mack"

    def test_datetime_midnight_start_date_end(self):
        """
        Test Google API edge case: start is a datetime at midnight but end is a date.
        """
        event = GoogleCalendarEvent(
            id="midnight_start_456",
            summary="All Day Meeting",
            description="Event starting at midnight",
            location="Office",
            attendees="",
            start=datetime(2024, 2, 5, 0, 0, 0, tzinfo=UTC),
            end=date(2024, 2, 6),
        )
        result = AbstractCalendarEvent.from_implementation(event)
        # Should be treated as an all-day event
        assert result.is_all_day is True
        assert result.start == datetime(2024, 2, 5, 0, 0, 0, tzinfo=UTC)
        assert result.end == datetime(2024, 2, 6, 0, 0, 0, tzinfo=UTC)
        assert result.title == "All Day Meeting"

    def test_date_start_datetime_non_midnight_end_raises(self):
        """
        Test that a date start with a non-midnight datetime end raises an error.
        This is a genuinely malformed event that can't be handled.
        """
        event = GoogleCalendarEvent(
            id="bad_event",
            summary="Bad Event",
            description="Inconsistent event",
            location="",
            attendees="",
            start=date(2024, 2, 2),
            end=datetime(2024, 2, 3, 14, 30, 0, tzinfo=UTC),  # Non-midnight time
        )
        with pytest.raises(ValueError) as exc_info:
            AbstractCalendarEvent.from_implementation(event)
        assert "non-midnight time" in str(exc_info.value)
        assert "Bad Event" in str(exc_info.value)

    def test_datetime_non_midnight_start_date_end_raises(self):
        """
        Test that a non-midnight datetime start with a date end raises an error.
        This is a genuinely malformed event that can't be handled.
        """
        event = GoogleCalendarEvent(
            id="bad_event_2",
            summary="Another Bad Event",
            description="Inconsistent event",
            location="",
            attendees="",
            start=datetime(2024, 2, 2, 10, 0, 0, tzinfo=UTC),  # Non-midnight time
            end=date(2024, 2, 3),
        )
        with pytest.raises(ValueError) as exc_info:
            AbstractCalendarEvent.from_implementation(event)
        assert "non-midnight time" in str(exc_info.value)
        assert "Another Bad Event" in str(exc_info.value)

    def test_same_day_all_day_event_raises(self):
        """Test that an all-day event with same start and end date raises an error."""
        event = GoogleCalendarEvent(
            id="same_day",
            summary="Same Day Event",
            description="Invalid",
            location="",
            attendees="",
            start=date(2024, 2, 2),
            end=date(2024, 2, 2),  # Same as start
        )
        with pytest.raises(ValueError) as exc_info:
            AbstractCalendarEvent.from_implementation(event)
        assert "same" in str(exc_info.value).lower()
        assert "at least one day apart" in str(exc_info.value)
