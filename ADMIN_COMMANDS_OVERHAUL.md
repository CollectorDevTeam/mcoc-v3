# MCOC Admin Commands Overhaul

## Overview
Updated the MCOC admin commands to provide comprehensive status reporting and improved sync data collection for all external data sources.

## Changes Made

### 1. **Status Command (`///admin status`)**
**Before:** Plain text output with inconsistent formatting; missing several data types  
**After:** Rich Discord embed with organized sections

**What's Now Reported:**
- **Last Sync Time** - When cache was last updated
- **API Connection Status** - Whether the API is connected
- **Core Data Counts:**
  - Champions
  - Abilities
  - Tags
  - Immunities
- **Extended Data Counts:**
  - Alliance War (AW)
  - Champions Map
  - Glossary Terms
  - Tierlist Champions
- **Prestige Data:**
  - Number of aggregated rows
  - Version hash
- **Version Hashes** - Full list of cached data version identifiers

**External Data Now Documented:**
The status command now comprehensively reports on all 9 external data sources tracked by the cache:
1. **Champions** - Champion character database
2. **Abilities** - Ability definitions
3. **Tags** - Champion tags/classifications
4. **Immunities** - Debuff immunity data
5. **Alliance War (AW)** - Alliance War mechanics and nodes
6. **Champions Map** - Champion family/relationship mapping
7. **Glossary** - Game terminology and definitions
8. **Tierlist** - Champion tier rankings from mcochub
9. **Prestige** - Player prestige data (aggregated by tier)

### 2. **Sync Command (`///admin sync`)**
**Before:** Basic text confirmation without data summary  
**After:** Rich embed with comprehensive data summary

**Improvements:**
- Displays sync status (Updated vs. Skipped)
- Reports exact counts for all 9 data sources
- Shows when sync completed
- Lists version hashes for all cached data
- Color-coded: Green for successful update, grey for no changes needed

**Data Reported:**
- All core data counts (Champions, Abilities, Tags, Immunities)
- All extended data counts (AW, Champions Map, Glossary, Tierlist)
- Version identifiers for all cached datasets

### 3. **Force Sync Command (`///admin force-sync`)**
**Before:** Only fetched and reported on core 4 data types; prestige handling was minimal  
**After:** Comprehensive multi-step fetch with full reporting on all data types

**New Capabilities:**
1. **All Data Types Fetched:**
   - ✅ Champions
   - ✅ Abilities
   - ✅ Tags
   - ✅ Immunities
   - ✅ Alliance War (NEW)
   - ✅ Champions Map (NEW)
   - ✅ Glossary (NEW)
   - ✅ Tierlist (NEW)
   - ✅ Prestige (enhanced)

2. **Real-time Progress Updates:**
   - Each data type shows "fetching..." status
   - Immediate update when fetch completes with count
   - Per-data-type progress in CacheStatusPoster UI

3. **Atomic Saves:**
   - All data saved atomically to cache
   - Prestige data specially handled with progress reporting
   - Fallback handling if individual data types fail

4. **Comprehensive Summary Embed:**
   - Completion timestamp
   - Core data section with 4-data summary
   - Extended data section with 4-data summary
   - Prestige status (Updated/Failed)
   - Organized, scannable format with bullet points

## Implementation Details

### External Data Processing Flow
```
API.get_champions()
API.get_abilities()
API.get_tags()
API.get_immunities()
API.get_aw()              ← NEW
API.get_champions_map()   ← NEW
API.get_glossary()        ← NEW
API.get_tierlist()        ← NEW
     ↓
Cache._diff_and_save()    (for each type)
     ↓
Cache.check_update_prestige()
     ↓
CacheStatusPoster embed summary
```

### Data Organization in Cache
The cache now maintains 9 distinct datasets:
- `champions.json` - Core champion data
- `abilities.json` - Ability definitions
- `tags.json` - Champion tags
- `immunities.json` - Immunity data
- `aw.json` - Alliance War data ← NEW
- `champions_map.json` - Champion relationships ← NEW
- `glossary.json` - Game terminology ← NEW
- `tierlist.json` - Tier rankings ← NEW
- `prestige.json` - Prestige aggregations

Each has a version hash tracked in `metadata.json`

## Benefits

1. **Visibility:** Admin can now see exactly what's being cached and when
2. **Debugging:** Easier to identify which data type is stale or problematic
3. **Completeness:** All 9 external data sources are now reported and synchronized
4. **User Experience:** Rich embeds are more readable than plain text
5. **Reliability:** Prestige syncing has enhanced reporting and error handling

## API Dependencies

The following API methods are now being used:
- `api.get_champions()` - Character database
- `api.get_abilities()` - Ability definitions
- `api.get_tags()` - Champion tags
- `api.get_immunities()` - Debuff immunity
- `api.get_aw()` - Alliance War mechanics ← NEW
- `api.get_champions_map()` - Champion relationships ← NEW
- `api.get_glossary()` - Game terminology ← NEW
- `api.get_tierlist()` - Tier rankings ← NEW (with fallback)
- `api.get_prestige()` - Player prestige data (via cache.check_update_prestige)

## Testing Checklist

- [ ] `/admin status` displays all 9 data type counts
- [ ] `/admin status` shows prestige row count and version
- [ ] `/admin sync` updates embed when new data is available
- [ ] `/admin sync` shows "Sync Skipped" when no changes needed
- [ ] `/admin force-sync` fetches all 9 data types
- [ ] `/admin force-sync` displays final summary with all counts
- [ ] `/admin force-sync` prestige updates show progress
- [ ] Embed formatting is consistent and readable
- [ ] Error handling works if any data fetch fails
- [ ] Version hashes are truncated properly in display
