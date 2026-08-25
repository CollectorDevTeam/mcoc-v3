# MCOC Command Map (Prefix Layer)

A concise, actionable map of the `///mcoc` prefix command tree (v2 → v3 migration checklist).
Use this to verify which commands are exposed by the prefix registrars and to spot missing or incomplete exports.

---

## Top level
**`///mcoc`**
- **Subcommands:** `status`
- **Description:** Root help and basic core status.

**`///mcoc status`**
- **Args:** none
- **Permission:** none
- **Description:** Shows whether core/cache attached.

---

## ///mcoc champ (champions)
- **`info`** — `* champion` — Show champion profile embed.
- **`abilities`** — `* champion` — Show champion abilities embed.
- **`synergies`** — `* champion` — Show champion synergies.
- **`tags`** — `* tag` — List champions with a tag.
- **`search`** — `* query` — Simple name/id search.
- **`calcstats`** — `champion, rarity, rank, sig?, ascended?, use_roster?` — Calculate statline (or use roster).

---

## ///mcoc roster (user roster)
- **`add`** — `champion, hargs` — Add champion to user roster.
- **`remove`** — `champion, hargs?` — Remove champion entries.
- **`update`** — `champion, hargs` — Update champion entry (rarity required).
- **`list`** — `hargs?` — Paginated roster view (PagesMenu).
- **`export`** — — Dump roster JSON (simple export).
- **`clear`** — — Delete user's roster/profile.

---

## ///mcoc admin (admin utilities)
- **`status`** — — owner — Cache / API / prestige summary.
- **`key`** — — owner — Show shared API key presence (masked).
- **`sync`** — — owner — Full cache sync (progress via queue).
- **`force-sync`** — — owner — Force immediate fetch/save of resources.
- **`prestige_sync`** — `force?` — owner — Run prestige update.
- **`dump`** — `kind key` — owner — Dump raw JSON for cache entry.

---

## ///mcoc account (user profiles & privacy)
- **`info` / `view`** — `member?` — Show profile embed or raw JSON.
- **`set`** — `field value` — Set allowed profile fields.
- **`link`** — `mcoc_id` — Link Discord → in‑game id.
- **`unlink`** — — Unlink in‑game id.
- **`delete`** — — destructive; **confirmation required** (PagesMenu.confirm).
- **`privacy`** — subgroup:
  - **`privacy mode`** — `mode` — Set privacy mode (private/guild/alliance/public).
  - **`privacy allow_guild`** — `guild_id` — Allow sharing with a guild.
  - **`privacy revoke_guild`** — `guild_id` — Revoke sharing with a guild.

---

## ///mcoc alliance (alliance management)
- **`info`** — — Show guild public alliance profile (alias of settings/info).
- **`create`** — `simple|complex name` — admin/manage_guild — Register alliance and create core roles (confirm).
- **`template`** — — admin/manage_guild — Interactive role template creation (confirm).
- **`setrole`** — `key @role` — admin/manage_guild — Link an existing role to a key.
- **`settype`** — `simple|complex` — admin/manage_guild — Change alliance type; create missing roles.
- **`setinfo`** — `field value` — leader/officer — Set alliance profile fields (name, tag, invite, about, started, poster, wartool).
- **`manage`** — — manager/leader/officer — Management overview and quick actions.
- **`join`** — — Add member to members role.
- **`leave`** — — Remove member from alliance roles.
- **`promote`** — `@member role_key` — leader — Assign battlegroup/officer roles.
- **`demote`** — `@member role_key` — leader — Remove configured role; update member_ids.
- **`addofficer`** — `@member` — leader — Add officer role and record id.
- **`removeofficer`** — `@member` — leader — Remove officer role and record id.
- **`listmembers`** — — public / officer view — Count for public; mentions for officers/leaders.
- **`reconcile`** — `apply?` — admin/manage_guild — Dry-run or fix missing configured roles.
- **`unregister`** — `remove_roles?` — admin/manage_guild — Unregister alliance (confirm; backup created).
- **`export`** — — admin/manage_guild — Export roster CSV (placeholder/unimplemented).
- **`profile`** — `@member?` — Per-user alliance profile (private view if in same guild).

---

## Gaps, priorities, and action items
1. **Registrar coverage**  
   Ensure each `register_with_group` wrapper re-exports every Cog command you want available under `///mcoc`. Some wrappers currently expose only a subset; add wrappers for missing commands (notably many alliance and account commands).

2. **Destructive confirmations**  
   Ensure `PagesMenu.confirm` is used in registrar wrappers for destructive actions (`account delete`, `alliance unregister`) and that `PagesMenu` is imported.

3. **Help text / docstrings**  
   Add short docstrings to each wrapper function so Red’s help system shows usage and examples.

4. **Idempotent registration**  
   Keep `_safe_add` pattern across all registrars to avoid `CommandRegistrationError` collisions.

5. **Export implementations**  
   Implement CSV export for alliance/roster `export` commands if required (file generation + upload).

6. **Permissions checks**  
   Ensure wrappers call helper checks (`is_leader`, `is_leader_or_officer`, `is_alliance_manager`) before performing privileged actions.

7. **Testing checklist**  
   - Restart bot; verify logs show registrars attached or commands skipped.  
   - Test `///mcoc alliance manage`, `///mcoc account set`, `///mcoc account delete` (confirm flow), `///mcoc roster list` (PagesMenu).  
   - Test leader-only flows with a test guild.

---

## Example `_safe_add` pattern (recommended)
```python
def _safe_add(cmd_name):
    def _decorator(func):
        try:
            if group.get_command(cmd_name):
                log.debug("Command %s already exists; skipping", cmd_name)
                return func
        except Exception:
            pass
        group.command(name=cmd_name)(func)
        return func
    return _decorator
