#!/usr/bin/env bash
#
# Replay this fork's changes onto a new upstream wger release.
#
#   extras/scripts/upgrade-upstream.sh <new-upstream-tag> [--no-tests]
#   .git/fork-upgrade.sh --continue [--no-tests]                # after fixing a conflict
#   extras/scripts/upgrade-upstream.sh --check                   # list vs. commits on this branch
#
# Never changes the fork branch itself: the result goes to upgrade/<tag>.
# See FORK-CHANGES.md.
#
# Settings (environment variables):
#   UPSTREAM_REMOTE  git remote of wger-project/wger   (default: upstream)
#   FORK_BRANCH      our long-lived branch              (default: sage)
#   OLD_BASE         upstream tag the branch is based on (default: read from FORK-CHANGES.md)

set -euo pipefail

UPSTREAM_REMOTE=${UPSTREAM_REMOTE:-upstream}
FORK_BRANCH=${FORK_BRANCH:-sage}
ROOT=$(git rev-parse --show-toplevel)
CHANGES="$ROOT/FORK-CHANGES.md"
GIT_DIR_ABS=$(cd "$(git rev-parse --git-dir)" && pwd)
STATE="$GIT_DIR_ABS/fork-upgrade-state"
# Mid-upgrade, the commit that adds this script may not be replayed yet, so --continue
# runs from a copy kept inside .git.
SELF_COPY="$GIT_DIR_ABS/fork-upgrade.sh"

die() { echo "error: $*" >&2; exit 1; }
say() { echo "==> $*"; }

old_base() {
    if [[ -n "${OLD_BASE:-}" ]]; then echo "$OLD_BASE"; return; fi
    sed -n 's/^- \*\*Upstream base:\*\* wger `\([^`]*\)`.*/\1/p' "$CHANGES" | head -1
}

# Prints "ID<TAB>match text" for every Active change in FORK-CHANGES.md
active_changes() {
    awk -F'|' '/^\| S-[0-9]{3} \|/ {
        id=$2; status=$4; match_text=$5
        gsub(/^ +| +$/, "", id); gsub(/^ +| +$/, "", status)
        gsub(/^ +| +$/, "", match_text); gsub(/`/, "", match_text)
        if (status == "Active") print id "\t" match_text
    }' "$CHANGES"
}

# Checks that every Active change has a commit in <base>..<head>
check_changes() {
    local base=$1 head=$2 missing=0 subjects
    subjects=$(git log --format=%s "$base..$head")
    while IFS=$'\t' read -r id text; do
        if grep -qF -- "$text" <<<"$subjects"; then
            echo "  ok       $id  ($text)"
        else
            echo "  MISSING  $id  (no commit title contains: $text)"
            missing=1
        fi
    done < <(active_changes)
    return $missing
}

run_tests() {
    say "Running the full test suite with settings.ci"
    (cd "$ROOT" && DJANGO_SETTINGS_MODULE=settings.ci python manage.py test)
}

finish() {
    local new_tag=$1 base=$2 tests=$3 report="$ROOT/upgrade-$1-report.txt"
    say "Comparing our old and new commits (git range-diff) -> $(basename "$report")"
    git range-diff --no-color "$base..$FORK_BRANCH" "$new_tag..HEAD" >"$report" || true
    cat "$report"

    say "Checking FORK-CHANGES.md against upgrade/$new_tag"
    if ! check_changes "$new_tag" HEAD; then
        die "some Active changes have no commit on upgrade/$new_tag. Bring them back or mark them Upstreamed/Dropped."
    fi

    rm -f "$STATE" "$SELF_COPY"
    if [[ "$tests" == yes ]]; then run_tests; fi

    cat <<EOF

Done. upgrade/$new_tag holds upstream $new_tag plus our changes. $FORK_BRANCH is unchanged.
Next:
  1. Read $(basename "$report"): every one of our commits should appear on both sides.
  2. Set "Upstream base" in FORK-CHANGES.md to $new_tag and commit it on upgrade/$new_tag.
  3. Push upgrade/$new_tag, review it, deploy it to a test environment.
  4. Tag the old branch (git tag archive/$FORK_BRANCH-$base $FORK_BRANCH) and push the tag.
  5. Move $FORK_BRANCH to upgrade/$new_tag. This rewrites $FORK_BRANCH, so it needs a force-push.
EOF
}

tests=yes
args=()
for a in "$@"; do
    case "$a" in
        --no-tests) tests=no ;;
        *) args+=("$a") ;;
    esac
done
set -- "${args[@]+"${args[@]}"}"

case "${1:-}" in
    "" | -h | --help)
        sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'
        ;;

    --check)
        base=$(old_base)
        [[ -n "$base" ]] || die "no Upstream base in FORK-CHANGES.md"
        say "Changes on $(git branch --show-current) since upstream $base"
        check_changes "$base" HEAD
        ;;

    --continue)
        [[ -f "$STATE" ]] || die "no upgrade in progress"
        read -r new_tag base <"$STATE"
        if [[ -d "$(git rev-parse --git-path rebase-merge)" || -d "$(git rev-parse --git-path rebase-apply)" ]]; then
            GIT_EDITOR=true git rebase --continue || die "still conflicting: fix, git add, then run --continue again"
        fi
        finish "$new_tag" "$base" "$tests"
        ;;

    *)
        new_tag=$1
        [[ -z "$(git status --porcelain --untracked-files=no)" ]] || die "commit or stash your changes first"
        base=$(old_base)
        [[ -n "$base" ]] || die "no Upstream base in FORK-CHANGES.md (or set OLD_BASE)"

        say "Fetching tags from $UPSTREAM_REMOTE"
        git fetch --quiet --tags "$UPSTREAM_REMOTE"
        git rev-parse --verify --quiet "$new_tag^{commit}" >/dev/null || die "unknown tag $new_tag"
        git rev-parse --verify --quiet "$base^{commit}" >/dev/null || die "unknown base tag $base"
        git rev-parse --verify --quiet "refs/heads/upgrade/$new_tag" >/dev/null && die "branch upgrade/$new_tag already exists"

        say "Our commits on $FORK_BRANCH since $base:"
        git log --oneline --no-merges "$base..$FORK_BRANCH"

        echo "$new_tag $base" >"$STATE"
        [[ "$(cd "$(dirname "$0")" && pwd)/$(basename "$0")" == "$SELF_COPY" ]] || cp "$0" "$SELF_COPY"
        chmod +x "$SELF_COPY"
        git switch --quiet -c "upgrade/$new_tag" "$FORK_BRANCH"
        say "Replaying them onto $new_tag"
        if ! git rebase --onto "$new_tag" "$base" "upgrade/$new_tag"; then
            cat <<EOF

Conflict. Fix the files git lists above, then:
  git add <files>
  $SELF_COPY --continue
(To give up: git rebase --abort; git switch $FORK_BRANCH; git branch -D upgrade/$new_tag)
EOF
            exit 1
        fi
        finish "$new_tag" "$base" "$tests"
        ;;
esac
