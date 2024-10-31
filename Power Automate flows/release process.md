# Internal release process

This is a "note to self" for how to release a new version of the Power Automate flow:

## Releasing the "master" flow

- In the PA platform, create a new copy of the flow for the release. Put the intended _version_ and "release" into the flow's title, e.g. `NG Outlook Google calendar sync v0.X - release`
- Edit the flow, carefully go through all settings, delete credentials, set reasonable defaults
- Save the flow
- In this folder, create a new folder for the version (e.g. `Power Automate flows/v0.X`)
- Export the flow as zip (Name: `NG Outlook Google calendar sync v0.X`, Description: `See https://github.com/MShekow/ng-outlook-google-calendar-sync`), put the downloaded zip file into the just-created `v0.X` folder
- Extract the just-downloaded zip. In `manifest.json` replace the email addresses (search for `@`) for both Outlook connections, the SharePoint connection and both Google connections
- Repackage the zip, put it in `Power Automate flows/v0.X/NG-Outlook-Google-calendar-sync-v0.X.zip`
- Pretty-print the JSON of `manifest.json` and `definition.json` and put it in `Power Automate flows/latest-source/`

## Release of the derived Outlook-only and Google-only flows

- In the PA platform, create two copies of the `NG Outlook Google calendar sync v0.X - release` flow, named `NG Outlook Google calendar sync v0.X - release - [Outlook|Google]-only` respectively
- Edit the flows:
  - Delete the non-needed blocks (including _settings_ blocks) that have `Google[-only]` or `Outlook[-only]` in their title
  - Save the flows
- Export the flows (use e.g. `NG Outlook sync v0.X` for the _Name_ field), put the zips in the `v0.X` folder
- Like above, extract the zips, clean the email addresses in the connections, then repackage the zips, name them `v0.X/NG-[Outlook|Google]-calendar-sync-v0.X.zip`
- Finally, update all links and the changelog in `<root>/README.md`
