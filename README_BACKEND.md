# README_BACKEND.md
## Backend architecture guide for the current MCOC codebase

This document describes the backend runtime used by the bot package in `mcoc/`. It focuses on how the shared system is initialized, how cached data is retrieved, and how the frontend command layers call into the canonical backend logic.

---

## High-level runtime flow

The runtime follows a thin frontend / rich backend split:

1. `mcoc/core.py` loads the bot package.
2. `mcoc/common/core.py` creates the shared runtime container and attaches it to `bot.mcoc_core`.
3. `mcoc/common/api/cache.py` loads or refreshes cached MCOC data.
4. `mcoc/common/api/cacheindex.py` builds lookup indexes for common query paths.
5. `mcoc/common/helpers/*` performs champion, roster, account, and data-transform logic.
6. `mcoc/prefix/*` and `mcoc/slash/*` render the results to Discord.

This keeps the actual behavior stable even when the user interacts through different command interfaces.

---

## Shared runtime container

The main shared object is `MCOCCommonCore`, defined in `mcoc/common/core.py`.

It provides:
- `bot` — the Red bot instance
- `cache` — a `CacheManager` instance
- `api` — an `MCOCHubAPI` wrapper
- `cacheindex` — the in-memory lookup index
- `ready` — async initialization state
- `async_init()` — loads cache data and builds indexes
- `close()` — cleans up API resources
- `health()` — quick subsystem summary

The package bootstrap calls `init_common_systems(bot)`, then stores the result on `bot.mcoc_core`.

---

## Cache layer

The cache layer lives under `mcoc/common/api/`.

### `cache.py`
This is the main cached-data orchestrator. It is responsible for:
- loading champion metadata
- tracking cache metadata and sync state
- exposing champion/tag/ability/immunity lookups
- retrieving prestige and tierlist data
- supplying normalization helpers used by the shared query logic

### `cacheindex.py`
This file builds lightweight in-memory indexes for fast access. It supports faster lookups for:
- champion-by-name
- champions-by-tag
- champions-by-ability
- immunity/tag normalization
- prestige lookups

This is the backend layer that makes filter evaluation efficient without pushing lookup semantics into the frontends.

---

## Business logic layer

The core behavior lives in `mcoc/common/helpers/`.

### `champions.py`
This file is the main canonical layer for champion search, filters, and tierlist rendering. It handles:
- direct-string token parsing
- canonical filter matching
- champion and tierlist page creation
- multi-step filter flows and pager-driven UI selection

### `roster.py`
This file manages roster parsing and display behavior, including:
- roster entry parsing
- filtering roster entries against canonical champion metadata
- profile and prestige synchronization paths

### `account.py`, `userdata.py`, `types.py`
These modules govern user data, account linkage, profile state, and the shared `Champion` domain model.

### `alliance.py`
Alliance-related logic sits in the shared helper layer, not in the Discord frontend modules.

---

## Utilities and parsing layer

### `utilities/query_parser.py`
This file converts raw user input into canonical filter tokens. It is the key site for handling raw text like:
- `bleed`
- `#cosmic`
- `mystic`
- `7-star`
- `6*`

This layer is intentionally backend-owned because it defines how input is interpreted across all command entry points.

### `utilities/hargs.py`
This file parses human-friendly argument forms and normalizes queries to the canonical shape used by the helper logic.

### `utilities/formatters.py`
This layer renders output-friendly strings and metadata produced by the backend so the UI can present them cleanly.

---

## Models and data contracts

The model layer in `mcoc/common/models/` defines structured shapes for:
- champion records
- app-level tierlist payloads
- upstream metadata used by helper logic

These models are not UI objects; they are data contracts for backend processing.

The important architectural point is that the frontend doesn't invent or reinterpret these structures directly. The backend owns the transformation into the canonical format that the UI can render.

---

## Frontend contract

The frontend packages should use the backend as a service layer.

Examples:
- `mcoc/prefix/champions.py` calls backend helpers to build filtered champion pages
- `mcoc/slash/champions.py` uses the same filtering behavior and renders a slash-specific view
- `mcoc/prefix/roster.py` and `mcoc/slash/roster.py` share roster logic from `common/helpers/roster.py`

The important rule is that the frontend should not own matching semantics or raw source normalization.

---

## Important invariants for future changes

When making backend changes, keep these rules in mind:

- all parsing and normalization should happen in `common/`, not in `prefix/` or `slash/`
- filter semantics should be centralized and re-used across search and roster flows
- cache and index logic should be treated as the single source of truth for external data
- embed/pager formatting may vary by frontend, but the underlying match logic should remain shared and consistent

---

## Practical mental model

The backend is best thought of as a three-stage pipeline:

1. Load and normalize source data (`common/api`)
2. Parse and evaluate user intent (`common/utilities` + `common/helpers`)
3. Format and display results (`prefix/` / `slash/`)

That separation is the main structural feature of this repo and is the model the current codebase follows.
