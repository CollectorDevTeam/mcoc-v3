# MCOC_STRUCTURE.md
## Structural index for the current repository

This document describes the actual repository layout used by the bot project today. It reflects the real package boundaries and shared responsibilities in the current tree, rather than the older template that assumed a single MCOC root package and a narrower set of modules.

---

## Repository top-level overview

### Root-level directories
- `mcoc/` — main bot package and runtime entrypoint
- `cdtcommon/` — shared utility package used by other modules
- `dadjokes/` — independent joke cog/module with its own logic and setup path
- `data/` — static cache and schema data used by MCOC logic
- `tests/` — regression tests covering filtering, parsing, and domain-model behavior
- `scripts/` — project scripts and utility automation
- `.venv/`, `.vscode/`, `.pytest_cache/` — local environment metadata, not source-of-truth code

### Repository-level responsibilities
- `mcoc/` owns the game bot runtime, caching, helper logic, and command frontends.
- `dadjokes/` is a standalone feature module rather than part of `mcoc/common`.
- `data/` provides cached content, schemas, and static metadata; it is consumed by the backend, not treated as an application layer.

---

## Package layout: `mcoc/`

### `mcoc/core.py`
**Purpose:** Bootstraps the package, initializes shared systems, attaches `bot.mcoc_core`, and registers the main feature cogs and optional modules.

### `mcoc/common/`
**Purpose:** Shared backend runtime used by all command frontends.

Contains:
- `api/` — cache access, API wrappers, prestige sync, and retrieval helpers
- `helpers/` — canonical application logic for champion search, roster flow, profiles, and account data
- `utilities/` — query parsing, token normalization, and display helpers
- `models/` — domain objects and structured metadata
- `feature_system/` — feature flags and entitlement logic
- `components/` — reusable pieces for UI and pager interactions
- `core.py` — shared runtime container for cache, API, and index objects

### `mcoc/prefix/`
**Purpose:** Legacy prefix command frontend.

Contains command entrypoints like:
- `account.py`
- `roster.py`
- `alliance.py`
- `champions.py`
- `admin.py`
- `core.py`

These are presentation layers that route into shared backend helpers and display results.

### `mcoc/slash/`
**Purpose:** Modern slash-command frontend.

Contains application command cogs and the slash root loader:
- `core.py`
- `champions.py`
- `roster.py`
- `admin.py`

The slash layer is intentionally thin and reuses the same shared business logic as the prefix layer.

### `mcoc/diagnostics/`
**Purpose:** Debug and inspection tooling for the bot runtime and cache.

This package is intended for inspection and developer troubleshooting, not for mutating production data.

---

## Shared backend breakdown

### `mcoc/common/api/`
Contains the data-access layer:
- `cache.py` — cache manager and champion/tag/ability/immunity metadata loading
- `cacheindex.py` — in-memory indexes used for fast lookups
- `api.py` — MCOCHub API wrapper / client layer
- `prestige.py` — prestige-related logic and sync support

This is where raw/cache-backed data is retrieved and normalized before being passed to helpers.

### `mcoc/common/helpers/`
Contains the behavior layer:
- `account.py` — account/profile and consent logic
- `alliance.py` — alliance-related helpers
- `champions.py` — champion filtering, tierlist generation, and pager helper logic
- `roster.py` — roster parsing, matching, and display flow
- `userdata.py` — user profile storage and access helpers
- `types.py` — domain model definitions such as `Champion`

This is the canonical location for bot behavior and matching logic.

### `mcoc/common/utilities/`
Contains shared utilities for parsing and output formatting:
- `query_parser.py` — raw input parsing into canonical filter tokens
- `hargs.py` — human-friendly argument parsing and normalization
- `formatters.py` — embed-friendly display helpers

These functions support both prefix and slash command flows without duplicating logic.

### `mcoc/common/models/`
Contains structured domain-data definitions,
including app-level metadata models such as tierlist payloads and upstream normalized objects.

The relevant structure is:
- `internal/`
- `mcochub/`
- `mcoc_app/`

### `mcoc/common/feature_system/`
Contains entitlement and feature rules used by the bot.

### `mcoc/common/components/`
Contains reusable UI building blocks used by the command frontends, such as page menus and embed helpers.

---

## Operational invariants

The current repo is organized around the following invariants:

1. `mcoc/common/` owns the actual business logic.
2. `mcoc/prefix/` and `mcoc/slash/` only present and orchestrate it.
3. Data access and normalization live in `common/api/` and `common/utilities/`.
4. Matching logic must be centralized so both roster and champion search use the same canonical filters.
5. Tierlist and champion search logic should operate on normalized champion metadata, not raw string fragments from a single data source.
6. Documentation should reflect the actual package structure and command topology, not an old intended layout.

---

## Directory map

```text
mcoc-v3/
├── mcoc/
│   ├── common/
│   │   ├── api/
│   │   ├── components/
│   │   ├── core.py
│   │   ├── feature_system/
│   │   ├── helpers/
│   │   ├── models/
│   │   └── utilities/
│   ├── diagnostics/
│   ├── prefix/
│   ├── slash/
│   ├── __init__.py
│   ├── core.py
│   └── README_COGS.md
├── cdtcommon/
├── dadjokes/
├── data/
├── scripts/
├── tests/
├── README_COGS.md
├── MCOC_STRUCTURE.MD
├── README_BACKEND.md
├── requirements.txt
└── LICENSE
```

---

## Documentation maintenance rule

Whenever a new backend helper, command module, or data source is introduced, the repo docs should be updated to reflect the change. The current architecture is explicit about boundaries; stale docs create false assumptions about where logic lives and where it should be edited.
