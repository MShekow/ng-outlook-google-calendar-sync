# Implementation notes

These are purely developer-oriented notes that e.g. discuss observations of the behavior of Power Automate actions, or discussing algorithm decisions.

## Notes about Power Automate behavior

- When retrieving events from either Google or Outlook, some of the fields have different names:
    - `iCalUId` in Outlook is `iCalUID` in Google, but we don't use it, because
      - 1. When we want to _delete_ or _update_ an event, we need to give the action the `id` value of the event, _not_ the iCal ID. 
      - 2. For _recurring_ Google events, the `iCalUID` value is always the same.
    - `subject` in Outlook is `summary` in Google
    - `body` in Outlook is `description` in Google
    - Regarding the _attendees_, Outlook has `requiredAttendees` and `optionalAttendees`, whereas Google has only `attendees`.
      - Multiple email addresses are separated by `,` in Google and by `;` in Outlook
      - Google does not preserve case-sensitivity of the attendees (everything is lower-cased), Outlook does preserve it
      - In Outlook, the value of `requiredAttendees` may be `some@email.com;` (that is, it may include a trailing unnecessary separator)
- Google events seem to lack fields that correspond to Outlook's `responseType`, `showAs` (e.g. "busy" or "free"), or `sensitivity`, thus these fields cannot be synchronized.
- Google's events have a `"status": "confirmed"` field whose meaning is unclear. It is _not_ the response type. I never managed to set it to `tentantive`, which is an allowed value. It seems to be the status of the meeting as defined by the _organizer_. It may (according to the docs) also have the value `cancelled`, which is pointless, because cancelled events are typically deleted and not returned by neither the Google nor the Outlook APIs.
- While Google's Create/Update blocks allow to set an `isAllDay` property, the response of the List block lacks such a property. Instead, you can derive whether a Google event is “all day” by looking at the start/end timestamp: in this case, it is just something like "2024-01-12" (the time is missing).
- The events of both APIs have a `start` and `end` field, but their content is different:
    - Outlook: "2024-01-06T12:30:00.0000000" (implicitly UTC, but lacks a timezone specifier, because events have a dedicated `timezone` field)
    - Google: "2024-01-05T19:15:00+00:00" (also UTC, which is explicitly stated)
    - Even though the timezone is normally not part of the start/end fields in Outlook, the Outlook create/update actions do accept timestamps that explicitly specify the timezone, e.g. "2024-01-05T19:15:00+00:00" or "2024-01-05T19:15:00Z"
- When creating calendar events with attendees, Outlook attempts to send invitation emails, while Google does not.
  - Trick: to avoid that Outlook sends invitation emails to non-existing locations (such as the `<prefix>@<event-id>.invalid` addresses we use to store the original event's ID), just use very long domain names (e.g. 100 characters or more). For unknown reasons, this causes the Outlook platform to _not_ send emails anymore 🤷‍♂️.
- When synchronizing two Outlook calendars, it can happen that their `body` field _always_ diverges, because the _server_ modifies the body _afterwards_! Examples include:
  - In the `<head><script>` section, the server adds code such as `div.WordSection1 {}`
  - In `<img>` tags in the `<body>`, the server adds attributes such as `data-imagetype`

Example for a **Google** event:

```json
{
    "kind": "calendar#event",
    "etag": "\"3408958702246000\"",
    "id": "80kavknn9rsth1nlvn09lef547",
    "status": "confirmed",
    "htmlLink": "https://www.google.com/calendar/event?eid=NzBrYXZrbm45cnN0aDFubHZuMDlsZWY1NDcgcGV0ZXJwYW45MTIxQG0",
    "created": "2024-01-05T18:28:58Z",
    "updated": "2024-01-05T18:29:11.123Z",
    "summary": "Blubb",
    "creator": "foo@gmail.com",
    "organizer": "foo@gmail.com",
    "start": "2024-01-05T19:15:00+00:00",
    "end": "2024-01-05T20:15:00+00:00",
    "iCalUID": "80kavknn9rsth1nlvn09lef547@google.com",
    "sequence": 4,
    "reminders": {
        "useDefault": true
    },
    "eventType": "default",
    "description": "",
    "location": "",
    "attendees": "",
    "endTimeUnspecified": false
}
```

Example for an **Outlook** event:

```json
{
    "subject": "SyncBlocker: Foo",
    "start": "2024-01-06T10:30:00.0000000",
    "end": "2024-01-06T11:00:00.0000000",
    "startWithTimeZone": "2024-01-06T10:30:00+00:00",
    "endWithTimeZone": "2024-01-06T11:00:00+00:00",
    "body": "blabla",
    "isHtml": true,
    "responseType": "organizer",
    "responseTime": "0001-01-01T00:00:00+00:00",
    "id": "AAMkAGRiOTlhZjY3LTQzNWUtNGM0Ny05MGMwLWFmNDBlNzAxMDQ5OQBGAAAAAADBo9O3K16XQLiK7AG7_ka5BwARhE7LLMewTpXLsn71Fh9UAADAKPwgAAARhE7LLMewTpXLsn71Fh9UAAFcosnNAAA=",
    "createdDateTime": "2024-01-05T17:47:36.6511836+00:00",
    "lastModifiedDateTime": "2024-01-05T17:47:38.7722417+00:00",
    "organizer": "m.shekow@sprinteins.com",
    "timeZone": "UTC",
    "iCalUId": "040000008200E00074C5B7101A82E0080000000074AEED44FF3FDA01000000000000000010000000E001E2DF8941C241A0C7E2D4D3F72718",
    "categories": [],
    "webLink": "https://outlook.office365.com/owa/?itemid=AAMkAGRiOTlhZjY3LTQzNWUtNGM0Ny05MGMwLWFmNDBlNzAxMDQ5OQBGAAAAAADBo9O3K16XQLoK7AG7%2Bka5BwARhE7LLMewTpXLsn71Fh9UAADAKPwgAAARhE7LLMewTpXLsn71Fh9UABFcosnNAAA%3D&exvsurl=1&path=/calendar/item",
    "requiredAttendees": "",
    "optionalAttendees": "",
    "resourceAttendees": "",
    "location": "",
    "importance": "low",
    "isAllDay": false,
    "recurrence": "none",
    "reminderMinutesBeforeStart": 15,
    "isReminderOn": false,
    "showAs": "busy",
    "responseRequested": true,
    "sensitivity": "normal"
}
```

## Algorithm decisions

- Filtering of old events in `/compute-actions`: we decided that, by default, `/compute-actions` only considers cal 1 or cal 2 events where `event.start >= <now>` holds. Otherwise, we could get duplicated (or disappearing) blocker events, when the events of cal1 and cal2 were retrieved from the provider APIs at different points of time, as illustrated by the following scenario:
  - Two flows are set up (#A and #B), using the _file-based_ approach (cal 2 events are imported via HTTP file)
  - Suppose there is an event from 8-9 AM, originating in calendar 2. The flows already synchronized this event some time in the past, e.g. in yesterday's execution (-> there is a corresponding blocker event in cal 1).
  - Suppose flow instance #A (that writes to calendar 1) always runs at 10 minutes _after_ the full hour, and flow instance #B (that writes to calendar 2) runs at 10 minutes _before_ the full hour.
  - By having #A filter out Blocker events and real events that happened before `<now>` (e.g. `<now> = 8:10 AM`), `compute-actions` won't add them to the `events_to_delete` list. Thus, we avoid that older blocker events are accidentally deleted.
  - By having #A filter out real calendar 2 events that happened before `<now>`, `compute-actions` won't add any corresponding blocker events to the `events_to_create` list. Thus, we avoid _duplicated_ blocker events that would have been created, just because the (already-existing) blocker event was not returned by the "Get ... calendar view of events cal1" action (that #A called at `8:10 AM`)
- The problem described above would only happen if the calendar 1 / 2 events were retrieved at (significantly) different points of time (which is only the case when using the _mirror file_ feature). Under normal circumstances, the calendar events are retrieved at (almost) the same time (maybe 1-2 seconds delay). To disable the filtering of old events, there is a `X-Disable-Past-Event-Filter` header. 
