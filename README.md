# Next-Generation Outlook + Google Calendar Sync

> [!CAUTION]
> I no longer actively maintain this project. See [here](https://github.com/MShekow/ng-outlook-google-calendar-sync/issues/20#issuecomment-2537932248) for details. It should continue to work, but I might not respond to help issues and will not develop any requested features. Since this is open-source software, PRs are welcome.

A Microsoft Power Automate flow to synchronize Outlook 365 calendars or Google calendars. All synchronization combinations are supported:
- Outlook 365 <-> Outlook 365 (within the same tenant, or across different tenants)
- Outlook 365 <-> Google
- Google <-> Google

> [!NOTE]  
> This flow requires that you pay for the Power Automate **Premium** plan because the flow makes HTTP requests using the Premium-only `HTTP` action!
>
> If you are looking for a solution that works with the _free_ plan of Power Automate, see https://github.com/MShekow/outlook-calendar-sync (Outlook 365 <-> Outlook 365) and https://github.com/MShekow/outlook-google-calendar-sync (Outlook 365 <-> Google). There is no version that supports Google <-> Google synchronization.

## Instructions & download

**Download** the most recent zip archive of the flow:
- To synchronize **Outlook 365** with **Google**: [download](https://github.com/MShekow/ng-outlook-google-calendar-sync/raw/refs/heads/main/Power%20Automate%20flows/v0.3/NG-Outlook-Google-calendar-sync-v0.3.zip)
- To synchronize **Outlook 365** with **Outlook 365**: [download](https://github.com/MShekow/ng-outlook-google-calendar-sync/raw/refs/heads/main/Power%20Automate%20flows/v0.3/NG-Outlook-calendar-sync-v0.3.zip)
- To synchronize **Google** with **Google**: [download](https://github.com/MShekow/ng-outlook-google-calendar-sync/raw/refs/heads/main/Power%20Automate%20flows/v0.3/NG-Google-calendar-sync-v0.3.zip)

If you want to clean/delete all blocker events:

- For **Google**, download [this](https://github.com/MShekow/ng-outlook-google-calendar-sync/raw/refs/heads/main/Power%20Automate%20flows/Delete%20SyncBlocker%20events%20(Google).zip) helper PowerAuto flow
- For **Outlook 365**, download [this](https://github.com/MShekow/ng-outlook-google-calendar-sync/raw/refs/heads/main/Power%20Automate%20flows/Delete%20SyncBlocker%20events%20(Outlook).zip) helper PowerAuto flow

Please see [this blog post](https://www.augmentedmind.de/2024/11/01/ng-calendar-sync-outlook-google/) for details and usage instructions.

## Changelog of Power Automate Flow

### v0.3 (2024-12-14)

* The _SharePoint_-based **HTTP** action (which was used by default because it was _free_) was replaced with the _Premium_ `Http` action. Reason: the SharePoint HTTP action no longer supports URLs that point to _non_-SharePoint servers
* Note: the v0.3 Power Automate flow is fully compatible with the v0.2.1 _sync helper service_! No corresponding v0.3 release is necessary for the _sync helper service_.

### v0.2 (2024-11-10) - **no longer works!**

* New setting to configure End-to-end encryption of uploaded / downloaded mirror files (Power Automate action _"Setting: cal1 upload or cal2 download encrypt or decrypt password (optional)"_)
* You can now use GitHub.com repositories as mirror file server

### v0.1 (2024-11-01) - **no longer works!**

Initial release.

## Changelog of sync helper service

### v0.2.1 (2024-11-20)

* New feature: endpoint `/compute-actions` supports a new _optional_ header `X-Disable-Past-Event-Filter` which can be set to "true". In this case, the algorithm considers _all_ submitted events, disabling the default behavior where it only considers cal 1 / 2 events for which `event.start >= <now>` holds

### v0.2 (2024-11-10)

* New feature: support for GitHub.com repositories for uploading and downloading mirror files. Files are created as regular commits to the repository
* New feature: endpoints `/retrieve-calendar-file-proxy` and `/extract-events` now support the header `X-Data-Encryption-Password`, encrypting / decrypting data downloaded from (or uploaded to) the location specified in the `X-File-Location` header

### v0.1 (2024-11-01)

Initial release.

## Running the _Sync helper service_

If you want to **self-host** the sync helper service, _Docker_ is recommended. There is a _Docker compose_ stack available.

To build the image and run the service, type `docker compose up -d`
To stop and clean up the service, type `docker compose down`

If you want SSL termination (e.g. using the free SSL certificates provided by Let's Encrypt), you need to put a reverse proxy (HTTP) server in front of the sync helper service. The reverse proxy then does the SSL termination. See e.g. [here](https://doc.traefik.io/traefik/user-guides/docker-compose/acme-tls/) for how to achieve this with Traefik, or [here](https://github.com/nginx-proxy/acme-companion) for how to use Nginx.

## Developing the _Sync helper service_

### Package management

The Python-based sync helper service uses [Poetry](https://python-poetry.org/) for package management. To avoid conflicts between the dependencies of Poetry and the dependencies of this project, you should either install Poetry by other means (e.g. with Brew), or use separate (virtual) environments, e.g. as follows (for UNIX):
- `python3 -m venv .poetry` to create Poetry's virtual env
- `./.poetry/bin/pip install -r requirements-poetry.txt` to install Poetry into that venv
- `python3 -m venv .venv` to create the project's venv
- `source .venv/bin/activate` to activate the project's venv
- `./.poetry/bin/poetry install --with test` (optional additional argument: `--sync`) to install/reinstall the dependencies with Poetry

### Running tests

Run `pytest tests` to run all unit or integration tests defined in the `tests` folder.
