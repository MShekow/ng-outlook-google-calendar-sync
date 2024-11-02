# Next-Generation Outlook + Google Calendar Sync

A Microsoft Power Automate flow to synchronize Outlook 365 calendars or Google calendars. All synchronization combinations are supported:
- Outlook 365 <-> Outlook 365 (within the same tenant, or across different tenants)
- Outlook 365 <-> Google
- Google <-> Google

## Instructions & download

**Download** the most recent zip archive of the flow:
- To synchronize **Outlook 365** with **Google**: [download](https://github.com/MShekow/ng-outlook-google-calendar-sync/raw/refs/heads/main/Power%20Automate%20flows/v0.1/NG-Outlook-Google-calendar-sync-v0.1.zip)
- To synchronize **Outlook 365** with **Outlook 365**: [download](https://github.com/MShekow/ng-outlook-google-calendar-sync/raw/refs/heads/main/Power%20Automate%20flows/v0.1/NG-Outlook-calendar-sync-v0.1.zip)
- To synchronize **Google** with **Google**: [download](https://github.com/MShekow/ng-outlook-google-calendar-sync/raw/refs/heads/main/Power%20Automate%20flows/v0.1/NG-Google-calendar-sync-v0.1.zip)

If you want to clean / delete all blocker events:

- For **Google**, download [this](https://github.com/MShekow/ng-outlook-google-calendar-sync/raw/refs/heads/main/Power%20Automate%20flows/Delete%20SyncBlocker%20events%20(Google).zip) helper PowerAuto flow
- For **Outlook 365**, download [this](https://github.com/MShekow/ng-outlook-google-calendar-sync/raw/refs/heads/main/Power%20Automate%20flows/Delete%20SyncBlocker%20events%20(Outlook).zip) helper PowerAuto flow

Please see [this blog post](https://www.augmentedmind.de/2024/11/03/next-gen-calendar-sync-for-outlook-and-google/) for details and usage instructions.

## Changelog of Power Automate Flow

### v0.1 (2024-11-01)

Initial release.

## Changelog of sync helper service

### v0.1 (2024-11-01)

Initial release.

## Developing the _Sync helper service_

### Package management

The Python-based sync helper service uses [Poetry](https://python-poetry.org/) for package management. To avoid conflicts between the dependencies of Poetry and the dependencies of this project, you should either install Poetry by other means (e.g. with Brew), or use separate (virtual) environments, e.g. as follows (for UNIX):
- `python3 -m venv .poetry` to create Poetry's virtual env
- `./.poetry/bin/pip install -r requirements.txt` to install Poetry into that venv
- `python3 -m venv .venv` to create the project's venv
- `source .venv/bin/activate` to activate the project's venv
- `./.poetry/bin/poetry install --with test` (optional additional argument: `--sync`) to install/reinstall the dependencies with Poetry

### Running tests

Run `pytest tests` to run all unit or integration tests defined in the `tests` folder.
