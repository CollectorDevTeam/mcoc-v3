You are GitHub Copilot assisting with the MCOC project inside the repo mcoc-v3.

Your job is to generate and maintain structured documentation files that help Copilot quickly establish context when editing code.

The MCOC cog lives at: mcoc-v3/MCOC
Other cogs exist at the repo root, each in their own directory.

=====================================================================
## REQUIRED METADATA HEADER FOR EVERY PYTHON FILE
=====================================================================

At the top of every .py file in MCOC (and other cogs), Copilot must insert or update the following header:

# Path: <relative path from repo root>
# File-Version: <semantic version, starting at 1.0>
# File-Id: <UUID that never changes even if file is renamed or moved>
# Purpose: <short description of what this file does>
# Public-API: <public classes/functions intended for external use>
# Internal: <internal helpers not meant for external use>
# Last-Modified: <YYYY-MM-DD>

Rules:
- File-Id is permanent. Copilot must preserve it even if the file moves or is renamed.
- File-Version increments when major changes occur.
- Last-Modified must be updated on every meaningful change.
- Purpose, Public-API, and Internal must be kept accurate.
- Copilot must never leave stale metadata.

=====================================================================
## DOCUMENTS YOU MUST GENERATE AND MAINTAIN
=====================================================================

1. MCOC_STRUCTURE.md  
   - The authoritative index describing the purpose of every directory and file in MCOC.
   - Must include:
     - Module Purpose Blocks (for each directory)
     - File Purpose Entries (3–5 lines each)
     - Cross-module relationships
     - Architectural rules
     - File-Id references for traceability

2. README_COGS.md  
   - Explain how cogs work in this repo.
   - Describe prefix vs slash frontends.
   - Describe how commands should call into common/.
   - Provide rules for adding new commands and avoiding duplication.
   - Include File-Id references for important cogs.

3. README_BACKEND.md  
   - Describe the backend architecture under /common.
   - Explain responsibilities of api/, helpers/, models/, utilities/.
   - Provide purity rules and data flow rules.
   - Include File-Id references for major backend modules.

4. COPILOT_BOOTSTRAP.md  
   - A short file telling Copilot which documents to load first.
   - Must list:
       - MCOC_STRUCTURE.md
       - README_COGS.md
       - README_BACKEND.md
   - Must state assumptions:
       - common/ = backend logic
       - prefix/ and slash/ = frontends
       - models/ = domain objects
       - diagnostics/ = debugging

=====================================================================
## WHEN TO UPDATE DOCUMENTS
=====================================================================

Copilot must update documentation whenever:
- A new file is created
- A file is renamed or moved (File-Id stays the same)
- A file’s purpose changes
- A new class or major function is added
- A directory is added or reorganized
- Architectural rules change

Copilot must NEVER leave documentation stale.

=====================================================================
## WHEN TO CREATE NEW DOCUMENTATION ENTRIES
=====================================================================

Copilot must automatically create new entries when:
- A new class is added
- A new module is added
- A new cog directory is added at repo root
- A new helper, model, or API file is added

=====================================================================
## FORMATTING RULES
=====================================================================

- Keep entries short, structured, and predictable.
- Avoid prose; use metadata-style blocks.
- Include File-Id for traceability.
- Do not generate human-oriented documentation; generate Copilot-oriented metadata.
- Do not duplicate content across files; each file has a single authoritative purpose entry.

=====================================================================
## OUTPUT FORMAT
=====================================================================

When asked to generate or update documentation:
- Produce the full updated file content.
- Do not produce diffs.
- Do not produce partial snippets.
- Always produce complete, ready-to-save files.

