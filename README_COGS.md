# README_COGS.md
## Repository governance for the current mcoc-v3 codebase

This repository is not organized as a set of independent "cogs" under a single root package. The active bot implementation is centered on the `mcoc/` package, with a few supporting utilities and standalone modules around it.

The current structure is intentionally layered:
- `mcoc/` is the bot package and primary application surface.
- `mcoc/common/` is the shared backend runtime and domain logic.
- `mcoc/prefix/` and `mcoc/slash/` are command frontends.
- `dadjokes/` is a separate standalone Red cog-style module that is not part of the shared MCOC runtime.
- `cdtcommon/` is a shared helper library used by other modules.
- `data/` holds cached or schema-driven MCOC content.
- `tests/` contains focused regression coverage for shared filtering and parsing behavior.

This file documents the actual architecture currently in use, not the older template that assumed a simpler monolithic cog layout.

---

## Core package boundaries

### `mcoc/`
`mcoc/` is the application package for the bot. It owns the package bootstrap, runtime attachment, and command registration. The most important pieces are:

- `mcoc/core.py` — package setup and registration of prefix, optional slash, and diagnostics modules
- `mcoc/common/` — backend runtime, cache/index logic, helpers, and shared models
- `mcoc/prefix/` — legacy prefix-command frontend layer
- `mcoc/slash/` — application-command frontend layer
- `mcoc/diagnostics/` — diagnostics and inspection tools

### `mcoc/common/`
`mcoc/common/` is the canonical backend. Frontend code should never contain business logic or data normalization rules. Shared responsibilities include:

- `common/api/` — cache access, API wrappers, prestige sync, and data fetching
- `common/helpers/` — business logic for roster, champion filters, account/profile work, and shared service orchestration
- `common/utilities/` — parsers, formatter helpers, and argument normalization
- `common/models/` — model definitions for MCOC data and app metadata
- `common/feature_system/` — entitlement and feature governance
- `common/components/` — reusable UI fragments used by the command frontends
- `common/core.py` — shared runtime container (`bot.mcoc_core`)

### `mcoc/prefix/` and `mcoc/slash/`
These directories are presentation layers only. They coordinate command flow, embed rendering, and user interaction; they do not own canonical data rules.

This is the rule that is now enforced in practice:
- parse + normalize + match data in `common/`
- format + display in `prefix/` or `slash/`
- reuse the same helper APIs across both frontends

---

## Architectural rules

### 1. Frontends stay thin
Frontends may:
- build Discord embeds and pagers
- route user input to backend helpers
- present results

Frontends must not:
- own canonical parsing logic
- duplicate filter logic
- re-implement champion matching rules
- normalize external data sources in place

### 2. Backend owns the canonical behavior
The shared logic in `mcoc/common/` is the source of truth for:
- cache metadata and cached data access
- champion/filter parsing
- data normalization across upstream sources
- roster matching and user profile logic
- tierlist and champion display formatting helpers

### 3. Diagnostics are read-only by default
The `mcoc/diagnostics/` area may inspect backend state and cached data, but it must not mutate production data as part of routine debugging.

### 4. The repo contains additional support modules, not parallel backends
The repository also contains modules like `dadjokes/` and `cdtcommon/` that are not part of `mcoc/common`. Those modules may provide utility behavior, but they are not a second MCOC business layer.

---

## Metadata and maintenance expectations

As the repo evolves, documentation and file-level metadata must remain aligned with the code. The project has adopted a metadata pattern with:

- `Path`
- `File-Version`
- `File-Id`
- `Purpose`
- `Public-API`
- `Internal`
- `Last-Modified`

This matters for three reasons:
1. It makes code ownership and intent explicit.
2. It supports safe, incremental refactors.
3. It keeps documentation close to the implementation that actually runs.

When a module changes shape, the docs should change with it.

---

## Current repo conventions

The active convention is:
- `mcoc/core.py` bootstraps the package and attaches `bot.mcoc_core`
- `mcoc/common/core.py` owns shared runtime state
- `mcoc/common/helpers/*` provides the canonical application logic
- `mcoc/prefix/*` and `mcoc/slash/*` are thin wrappers over that shared logic
- `data/` is a cache and schema source, not a backend package

This means the repo is best understood as a hybrid bot package:
- one main shared backend feature package, plus
- a set of smaller utility modules and independent command modules.

---

## Summary

The practical source of truth for the project is the `mcoc/` package and the shared runtime under `mcoc/common/`.

The core invariant is simple:
- shared logic belongs in `mcoc/common/`
- user-facing command code belongs in `mcoc/prefix/` or `mcoc/slash/`
- repo docs must describe the real package boundaries, not a legacy template

If new modules are added, they should be documented in terms of the actual runtime architecture above, not as another replacement for the original monolithic cog layout.
