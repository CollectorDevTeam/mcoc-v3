# COPILOT_BOOTSTRAP.md
## Copilot Bootstrap Instructions for mcoc-v3

This file tells GitHub Copilot how to initialize context when working inside the `mcoc-v3` repository.  
Copilot must load this file first, then load the referenced documents, then read file-level metadata headers.

---

## Load Order

When Copilot begins a conversation involving this repository, it must load the following documents in this exact order:

1. MCOC_STRUCTURE.md  
2. README_COGS.md  
3. README_BACKEND.md  

After loading these documents, Copilot must read the metadata header at the top of any file being edited.

---

## Required File Metadata Header

Every `.py` file in every cog must begin with:

# Path: <relative path from repo root>
# File-Version: <semantic version, starting at 1.0>
# File-Id: <UUID that never changes even if file is renamed or moved>
# Purpose: <short description of what this file does>
# Public-API: <public classes/functions intended for external use>
# Internal: <internal helpers not meant for external use>
# Last-Modified: <YYYY-MM-DD>
# Used-By: <comma-separated list of modules that import or depend on this file>

Copilot must use this metadata to understand file-level context and dependency relationships.

---

## Architectural Assumptions

Copilot must assume the following structure for the current repository:

- `mcoc/` is the main bot package and source of truth for the application runtime.
- `mcoc/common/` is the canonical backend layer for the bot.
- `mcoc/prefix/` and `mcoc/slash/` are **frontends**.
- `mcoc/diagnostics/` contains **developer diagnostics**.
- `mcoc/common/models/` defines **canonical domain objects**.
- Supporting modules like `dadjokes/`, `cdtcommon/`, and `data/` are not parallel backend layers for the MCOC package.
- Frontends must stay thin and delegate business logic to the shared backend.

---

## Behavioral Requirements

Copilot must:

- Respect backend/frontend boundaries.
- Place new backend logic only in `mcoc/common/`.
- Place new frontend logic only in `mcoc/prefix/` or `mcoc/slash/` unless the module is a separate standalone feature.
- Never introduce business logic into frontends.
- Never introduce Discord formatting into backend.
- Preserve File-Id UUIDs across renames and moves.
- Update documentation when structure or responsibilities change.
- Keep metadata headers accurate and synchronized.
- Populate `# Used-By:` with the actual importer modules for each file when that dependency list is known.

---

## When Copilot Must Update Documentation

Copilot must update:
- MCOC_STRUCTURE.md
- README_COGS.md
- README_BACKEND.md
- File metadata headers

Whenever:
- A new file is created
- A file is renamed or moved
- A cog is added or reorganized
- Backend responsibilities change
- Frontend responsibilities change

---

## Purpose of This Bootstrap File

This file ensures Copilot always begins with:
- The correct architectural model for the current repo
- The correct backend/frontend separation
- The correct documentation set
- The correct metadata expectations, including `# Used-By:`

Copilot must treat this file as the authoritative bootstrap for all conversations involving this repository, and it should stay aligned with the real code layout rather than older assumptions.
