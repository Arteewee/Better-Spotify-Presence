# Better Spotify Presence — Engine Freeze

## Frozen Engine Version

- App version: 2.9.5
- Engine version: 1.0.0
- Status: Frozen

## Core Files

- spotify.py
- lyrics.py
- lyrics_providers.py
- lyrics_persistent_cache.py
- rpc.py
- sync_engine.py
- cache.py
- state_store.py
- diagnostics.py
- config.py
- main.py

## Stable Features

- Spotify profile switching
- Spotify OAuth cache per profile
- Spotify rate-limit guard
- Persistent Retry-After cooldown
- Adaptive Spotify polling
- Local playback clock
- Smooth drift correction
- Anti flick-back
- Background lyrics loader
- Background retry
- Multi lyrics provider
- Smart provider ranking
- Metadata matching
- Confidence scoring
- Memory lyrics cache
- Offline persistent lyrics cache
- Dynamic lyric emoji
- Section detection
- Instrumental detection
- Dynamic album artwork
- Discord progress timer
- Spotify and source-code buttons
- Rich Presence payload optimizer
- Diagnostics

## Freeze Rules

1. Core files may only be modified for confirmed bugs, security issues, or provider/API compatibility.
2. New GUI, tray, updater, installer, and settings features must be implemented outside the core engine.
3. Every core change must increase `ENGINE_VERSION`.
4. A core change must pass the engine test checklist before merge.
5. Experimental features must not be added directly to frozen engine files.

## Engine Test Checklist

- Application starts without exception.
- Discord RPC connects.
- Spotify active profile is correct.
- Current song is detected.
- Song changes do not flick back.
- Timer does not reset when lyrics change.
- Lyrics load without blocking playback.
- Provider timeout does not freeze the loop.
- Provider fallback works.
- Offline cache works after restart.
- Seek triggers correct clock sync.
- Pause clears activity after configured polls.
- Spotify HTTP 429 activates persistent cooldown.
- Restart restores cooldown without new Spotify requests.
- RPC skips identical payloads.
