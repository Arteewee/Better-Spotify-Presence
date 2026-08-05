# Better Spotify Presence — v2.11.0

Release date: 2026-08-06

## Highlights

Version 2.11.0 upgrades Better Spotify Presence from a Python script into a more complete desktop application foundation with a graphical interface, runtime controls, diagnostics, multi-profile support, logging, crash recovery, and an integrated auto-updater.

## Added

### Desktop application

- PySide6 desktop interface.
- System tray integration.
- Start, pause, resume, and stop controls.
- Live song metadata, progress, and synchronized lyric display.
- Runtime status bar for Engine, Spotify, Lyrics, and Discord RPC.
- Dashboard, Settings, and Log Viewer windows.
- Console-less launcher support through `SpotifyPlus.pyw`.

### Live Lyrics Engine

- Local lyric clock independent from Spotify polling frequency.
- Background lyric loading.
- Protection against stale lyric results after rapidly changing songs.
- Multi-provider lyric lookup.
- Metadata matching and confidence scoring.
- Memory and persistent offline lyric cache.
- Adaptive Spotify polling near the end of a track.
- Lyrics remain synchronized while Spotify API requests are in cooldown.

### Spotify Profiles

- Unlimited Spotify Developer profiles.
- Add, rename, duplicate, edit, delete, and activate profiles.
- Separate OAuth cache for every Spotify profile.
- Automatic migration from the legacy `.env` profile format.
- Restart flow after changing active credentials.

### Diagnostics and Logging

- Central thread-safe logger.
- Daily rotating log files.
- Realtime Log Viewer with level and category filters.
- Event bus and global runtime status manager.
- Internal toast notification queue.
- Fatal error dialog with:
  - Restart Spotify+
  - Open Logs
  - Copy Error
  - Close
- Global exception handling for the main thread and background threads.

### Auto Updater

- GitHub Releases update source.
- Stable, Beta, and Nightly channels.
- Background update checks.
- Manual “Check for Updates” button.
- Update Available dialog with release notes.
- Background package download with progress and cancellation.
- SHA-256 integrity verification.
- Secure ZIP validation.
- Protection against path traversal and symbolic links.
- Backup before installation.
- Automatic restart after applying an update.
- Rollback when installation fails.
- Backup retention and update result messages.

## Improved

- Reduced Spotify API request frequency without slowing the live lyric clock.
- Better song-change detection.
- More reliable Discord RPC reconnect behavior.
- Cleaner Settings workflow.
- Improved GUI layout and minimum sizing.
- Better handling for Spotify API rate limits.
- Improved application shutdown and logger flushing.
- Safer background worker lifecycle.

## Security

- Spotify and Discord credentials remain outside source control.
- Update packages are verified using SHA-256.
- Update ZIP files are checked before extraction.
- Downgrades are rejected by the updater.
- Unsafe archive paths and symbolic links are rejected.

## Important setup notes

Do not commit or include these files in release packages:

- `.env`
- `profiles.json`
- OAuth token cache files
- `settings.json`
- log files
- virtual environments
- `__pycache__`
- downloaded update files

User data remains stored under:

```text
%LOCALAPPDATA%\BetterSpotifyPresence
```

## Known limitations

- The V2 updater is primarily prepared for Windows.
- The packaged updater helper executable will be finalized during V3 packaging.
- Theme Manager is postponed until after the V3 stable release.
- The first public update package must be uploaded manually to GitHub Releases.

## Upgrade notes

The application version is now:

```text
2.11.0
```

The engine remains frozen at:

```text
1.0.0
```

## Next milestone

- V2.10.7 Final UI Polish
- V3 Packaging and Deployment
