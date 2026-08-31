# CollectorVerse MCOC Bot Privacy Policy

**Effective date:** 2026-08-31  
**Repository path:** `mcoc-v3/mcoc/privacy_policy.md`  
**Repository:** https://github.com/CollectorDevTeam/mcoc-v3

## 1. Introduction
CollectorVerse (“we”, “us”, “our”) provides a Discord bot and related services (the “Service”) that help users manage and display Marvel Contest of Champions (MCOC) roster and profile information. This Privacy Policy explains what information we collect, how we use it, how we share it, and the choices you have about your information.

## 2. Scope
This policy applies to personal data collected or processed when you interact with the CollectorVerse MCOC bot on Discord, including when you create a profile, link an in‑game account, or use roster and prestige features.

## 3. Information We Collect
We collect only the information necessary to provide the Service:

- **Profile data**: display name, in‑game username (`mcoc_name`), in‑game id/slug (`mcoc_id`), website, timezone, alliance, job/role, age (optional), gender (optional), short bio (`about`), mastery link, and playing‑since date.
- **Roster data**: champion slug, rarity (stars), rank, signature level, ascension, tags, and any user‑entered raw roster text.
- **Computed data**: prestige values, top‑5 champions, cached aggregates derived from roster and prestige tables.
- **Consent metadata**: whether you agreed to this policy, timestamp of consent, policy version or commit SHA, and consent source URL.
- **Operational metadata**: timestamps of profile updates, and minimal audit logs for consent and deletion actions.
- **Non‑personal telemetry**: optional diagnostic logs (errors, sync status) that do not contain PII.

We do not collect or store passwords, payment information, or private messages from Discord.

## 4. How We Use Your Information
We use collected data to:

- Build and display your CollectorVerse profile and roster pages.
- Compute prestige and top‑5 champion lists.
- Provide search, filtering, and roster comparison features.
- Persist user preferences and consent status.
- Maintain and improve the Service (debugging, cache syncs, and analytics).
- Comply with legal obligations and respond to user requests (e.g., deletion).

We do not use your data for advertising or sell it to third parties.

## 5. Sharing and Disclosure
We will not share your personal data with third parties except:

- **Service providers**: third‑party hosting or tooling providers that process data on our behalf under contract.
- **Legal requirements**: when required by law or to respond to lawful requests.
- **User requests**: when you request deletion or export of your data.

If we ever plan to share data for other purposes, we will notify you and obtain consent where required.

## 6. Data Retention and Deletion
- We retain profile and roster data while your account exists and for a reasonable period after you revoke consent or request deletion to allow for recovery and audit.
- On **consent revocation** or **account deletion**, we will delete profile and roster data from our primary storage and caches within a reasonable timeframe and log the deletion event for audit (without retaining the deleted personal data).
- Backups may persist for a limited time; we will remove personal data from backups according to our retention schedule.

## 7. Your Rights and Choices
- **Access**: You can request a copy of the profile data we hold about you.
- **Correction**: You can update profile fields via the bot commands.
- **Deletion**: You can revoke consent and request deletion of your profile and roster (`///account revoke-consent` or similar).
- **Consent**: You must explicitly agree to this policy before we create or store your profile data. We will record consent metadata.

To exercise any of these rights, use the bot commands or contact the maintainers via the repository.

## 8. Security
We implement reasonable administrative, technical, and physical safeguards to protect your data. However, no system is completely secure; we cannot guarantee absolute security.

## 9. Children
The Service is not intended for children under 13. We do not knowingly collect personal data from children under 13. If you believe we have collected such data, contact us to request deletion.

## 10. Changes to This Policy
We may update this policy. When we do, we will update the `consent_version` and `consent_source` and, if required, prompt users to re‑consent. The policy’s effective date will be updated.

## 11. Contact
For questions about this policy or to exercise your rights:
- **Repository**: https://github.com/CollectorDevTeam/mcoc-v3  
- Open an issue in the repo or contact the bot maintainers via the project contact listed in the repository.
