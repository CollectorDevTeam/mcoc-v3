# MCOC Cog Architecture — README

## Purpose
This document describes the high-level structure and responsibilities of the MCOC cog repository, the public API surfaces, and conventions for contributors.

## Top-level layout
- `mcoc/common/` — shared logic and utilities.
  - `api/` — network, cache, prestige; external data sources.
  - `helpers/` — business logic used by frontends (public surface).
  - `feature_system/` — entitlements and gating.
- `mcoc/prefix/` — legacy prefix command cogs (/// commands).
- `mcoc/slash/` — modern application command cogs (slash commands).
- `mcoc/diagnostics/` — debug and diagnostics helpers.

## Design principles
1. **Single source of truth for user data**: `helpers.userdata.UserDataManager` is the canonical manager for per-user storage.
2. **Frontends import only from `mcoc.common.helpers` and `mcoc.common.api`**.
3. **No cross-imports from `prefix`/`slash` into `common`**.
4. **Public vs internal**: `helpers/__init__.py` exports the stable API. Internal helpers are prefixed with `_`.
5. **File headers & versioning**: Every file must include the standard header (Path, File-Version, File-Id, Purpose, Public-API, Last-Modified, Changelog).
6. **Breaking changes**: Bump `File-Version` MAJOR and update changelog.

## Public API (stable)
- `mcoc.common.helpers.get_user_manager()`
- `mcoc.common.helpers.UserDataManager` (methods: `add_champion`, `remove_champion`, `update_champion`, `list_roster`, `get_profile`, `set_profile_field`, `delete_user`)
- `mcoc.common.helpers.user_has_consented(parent, user_id)`
- `mcoc.common.api.CacheManager`, `CacheIndex`, `MCOCHubAPI`, `PrestigeManager`

## How to add a new helper
1. Add file under `mcoc/common/helpers/`.
2. Add header metadata.
3. Add the exported names to `mcoc/common/helpers/__init__.py`.
4. Write unit tests and update changelog.

## Release & deployment
- Keep `mcoc` as a single cog package for Red; use `setup.py`/`pyproject.toml` at repo root for packaging.
- For breaking API changes, document migration steps in the changelog and update `README_COGS.md`.

