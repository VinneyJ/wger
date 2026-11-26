# Changes in this fork

This fork (`VinneyJ/wger`, branch `sage`) is upstream wger plus a short list of our own
changes. This file is the list. Keep it up to date: every change we make gets a row, and
every row says how we know it still works.

- **Upstream base:** wger `2.7`
- **Upgrade to a new upstream release:** `extras/scripts/upgrade-upstream.sh <tag>` (see below)
- **Check this list against the branch:** `extras/scripts/upgrade-upstream.sh --check`

## The list

| ID | Change | Status | Commit title contains | Guarded by | Upstream |
|---|---|---|---|---|---|
| S-001 | Remove the marketing, docs and API-docs pages and the "About this software" menu; one "About & licences" page; source link points to this fork; logged-out `/` goes to sign-in | Active | `Remove docs and marketing pages, consolidate licences into About page` | `wger/core/tests/test_about.py`, `wger/core/tests/test_fork_changes.py` | Ours only |
| S-002 | Provisioning API for trusted service accounts (`/api/v2/provisioning/…`) | Active | `Add a provisioning API for trusted service accounts` | `wger/core/tests/test_provisioning_api.py` | Could be offered upstream |
| S-003 | This list, the fork checks and the upgrade script | Active | `[S-003]` | `wger/core/tests/test_fork_changes.py` | Ours only |
| S-004 | CORS also on the token-based app sign-in API (`/allauth/app/`), with `X-Session-Token` allowed, so browser apps on another domain can sign in; cookie pages stay same-origin | Active | `[S-004]` | `wger/core/tests/test_cors_app_auth.py` | Could be offered upstream |
| S-005 | Tests and builds our image from `sage` (`.github/workflows/sage-image.yml`), published as `ghcr.io/vinneyj/wger-server:sage-<commit>` for homelab | Active | `[S-005]` | `wger/core/tests/test_sage_image.py` | Ours only |
| S-006 | Provisioning API gives out the API key of a user the service account created (`POST /api/v2/provisioning/user/<id>/api-key/`), so Sage can coach gym members who join with a code | Active | `[S-006]` | `wger/core/tests/test_provisioning_api.py` | Could be offered upstream (with S-002) |
| S-007 | `api/v2/userprofile/` reads and writes the member's `first_name` and `last_name` (on the user), so apps can edit names | Active | `[S-007]` | `wger/core/tests/test_user_profile_api.py` | Could be offered upstream |

**Status** is one of:
- `Active`: on the branch; the upgrade script and tests make sure it stays.
- `Pending (PR #n)`: not merged yet. Switch to `Active` in the same PR that merges it.
- `Upstreamed (wger <version>)`: upstream now has it; our commit is dropped during the next upgrade.
- `Dropped`: we removed it on purpose (say why in the row).

## Rules for new changes

1. Give it the next free ID and put `[S-00N]` at the start of the commit title.
2. Add a row here in the same PR, with at least one test that fails if the change is lost.
3. Prefer new files and small hooks into upstream files (for example one line in `urls.py`)
   over editing upstream code in place. Fewer edits to upstream files means fewer conflicts.
4. Merge PRs with **"Rebase and merge"**, so each change stays a separate commit that the
   upgrade script can replay. (Older merge commits are fine: the script skips them and replays
   the commits inside.)
5. Generic improvements are worth offering upstream. Once accepted, mark the row `Upstreamed`.

## Upgrading to a new upstream release

```sh
git remote add upstream https://github.com/wger-project/wger.git   # once
extras/scripts/upgrade-upstream.sh 2.8
```

The script:

1. fetches upstream tags and creates `upgrade/<tag>` from the new tag;
2. replays our commits (everything on `sage` since the old base) onto it, stopping on conflicts:
   fix them, `git add` the files, then run `.git/fork-upgrade.sh --continue` (a copy the
   script keeps, because our own commits, including the script, are still being replayed);
3. compares the old and new list of commits with `git range-diff` and writes the report to
   `upgrade-<tag>-report.txt`;
4. checks that every `Active` change in this file still has its commit;
5. runs the full test suite with `settings.ci` (skip with `--no-tests`).

`sage` itself is never changed by the script. When the report and tests look right, update
"Upstream base" above, review the branch, tag the old `sage` (`archive/sage-<old base>`), and move `sage` to it. Moving `sage` rewrites it, so it needs a force-push: do it on purpose, after review.
