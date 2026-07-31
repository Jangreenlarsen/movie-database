# Changelog

Nyeste øverst. Hver entry tagges med `[version build NNNN]` (jf. CLAUDE.md regel 4).

## [0.1.0 build 0001] — 2026-07-31 — Projekt-scaffold

- Oprettet `CLAUDE.md` (system-prompt), `version.json`, `ARCHITECTURE.md`, `MOVIE_API_REFERENCE.md`, `TECH_REFERENCE.md`, `FEATURES.md`, `BUGS.md`, `RELEASE_NOTES.md`.
- Valgt stack: React (Vite, PWA) frontend, Python/FastAPI backend, MongoDB database.
- Valgt scan-flow: UPC/EAN-stregkode-scanning i browseren → UPC-opslag → TMDb-metadata-bekræftelse.
- Oprettet minimal backend-skelet (FastAPI + Motor + health-endpoint) og frontend-skelet (React/Vite PWA).
- Docker Compose-fil til backend + frontend + MongoDB.
- `.claude/settings.local.json` med læse/skrive-rettigheder til projektmappen.
