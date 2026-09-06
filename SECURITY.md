# Security policy

## Supported versions

The `main` branch is supported.

## What this project can affect

R-Ctrl records microphone audio, transcribes it locally, pastes into the
focused window (clipboard + Ctrl+V), and can bind a global hotkey (UAC).
The optional FastAPI server binds to `127.0.0.1` only and does not inject
keystrokes.

Do not bind the server to `0.0.0.0` without token auth and TLS.

## Reporting a vulnerability

Do not open a public issue.

1. Use [GitHub Security Advisories](https://github.com/polyfoil/R-Ctrl/security/advisories/new), or
2. Contact the maintainer via their GitHub profile if advisories are unavailable.

Include: mode (widget / server), OS build, and whether the report involves
hotkey injection, localhost exposure, or model/cache paths.
