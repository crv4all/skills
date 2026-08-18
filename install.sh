#!/bin/sh
# install.sh -- install CRV agent skills into your harness.
#
# POSIX shell. The only external dependency is git, and only when installing
# from the remote. That is deliberate: an installer with dependencies replaces
# the user's problem with an installation problem, at the moment they were
# trying to get something else done.
#
#   ./install.sh --list
#   ./install.sh --skill crv-codebase-onboarding
#   ./install.sh --all --target project --harness claude,cursor
#
# Run with --help for everything.
#
# Exit codes:
#   0  success (including a dry run)
#   1  refused: a locally modified skill would be overwritten (use --force)
#   2  usage error
#   3  a required input is missing (git, source, or an unknown skill)
#   4  the source checkout is malformed
#   5  internal error

set -eu

REPO_URL="${CRV_SKILLS_REPO:-https://github.com/crv4all/agent-skills.git}"
REPO_REF="${CRV_SKILLS_REF:-main}"
CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/crv-agent-skills"
STAMP_FILE=".crv-install"

SOURCE_DIR=""
TARGET="personal"
HARNESSES=""
EXPLICIT_DIR=""
SELECTED=""
WANT_ALL=0
DRY_RUN=0
FORCE=0
DO_LIST=0
QUIET=0

EXIT_OK=0; EXIT_REFUSED=1; EXIT_USAGE=2; EXIT_INPUT=3; EXIT_MALFORMED=4

log()  { [ "$QUIET" -eq 1 ] || printf '%s\n' "$*" >&2; }
warn() { printf 'warning: %s\n' "$*" >&2; }
err()  { printf 'error: %s\n' "$*" >&2; }
die()  { err "$2"; exit "$1"; }

usage() {
  cat >&2 <<'END_USAGE'
install.sh -- install CRV agent skills

USAGE
  ./install.sh [options]

SELECTION
  --list                  Print the available skills and exit. Writes nothing.
  --skill NAME            Install one skill. Repeatable.
  --all                   Install every skill.

DESTINATION
  --target personal       Install for your user (default).
  --target project        Install into the current repository, to be committed.
  --harness LIST          Comma-separated: claude, cursor, copilot, codex, agents.
                          Default: auto-detect from directories that already exist.
  --dir PATH              Install into PATH directly, ignoring --harness/--target.

SOURCE
  --source PATH           Use a local checkout instead of cloning.
  --ref REF               Git ref to install from (default: main).

BEHAVIOUR
  --dry-run               Print what would happen. Writes nothing.
  --force                 Overwrite skills that have been modified locally.
  --quiet                 Only warnings and errors.
  -h, --help              This text.

NOTES
  A skill you have edited locally is skipped with a warning rather than
  overwritten. A silent overwrite of somebody's fix is worse than an
  out-of-date skill.

  The layer directory (utilities/knowledge/patterns/processes) is a CRV
  organizing convention. Harnesses take a skill's identity from the directory
  that directly contains SKILL.md, so installs are flattened.

EXAMPLES
  ./install.sh --list
  ./install.sh --skill crv-create-skill --harness claude
  ./install.sh --all --target project --harness copilot --dry-run
  ./install.sh --all --dir ~/.agents/skills
END_USAGE
}

# --------------------------------------------------------------------------
# Arguments
# --------------------------------------------------------------------------

while [ $# -gt 0 ]; do
  case "$1" in
    --list) DO_LIST=1 ;;
    --all) WANT_ALL=1 ;;
    --skill) [ $# -ge 2 ] || die $EXIT_USAGE "--skill needs a value"
             SELECTED="$SELECTED $2"; shift ;;
    --skill=*) SELECTED="$SELECTED ${1#--skill=}" ;;
    --target) [ $# -ge 2 ] || die $EXIT_USAGE "--target needs a value"
              TARGET="$2"; shift ;;
    --target=*) TARGET="${1#--target=}" ;;
    --harness) [ $# -ge 2 ] || die $EXIT_USAGE "--harness needs a value"
               HARNESSES="$2"; shift ;;
    --harness=*) HARNESSES="${1#--harness=}" ;;
    --dir) [ $# -ge 2 ] || die $EXIT_USAGE "--dir needs a value"
           EXPLICIT_DIR="$2"; shift ;;
    --dir=*) EXPLICIT_DIR="${1#--dir=}" ;;
    --source) [ $# -ge 2 ] || die $EXIT_USAGE "--source needs a value"
              SOURCE_DIR="$2"; shift ;;
    --source=*) SOURCE_DIR="${1#--source=}" ;;
    --ref) [ $# -ge 2 ] || die $EXIT_USAGE "--ref needs a value"
           REPO_REF="$2"; shift ;;
    --ref=*) REPO_REF="${1#--ref=}" ;;
    --dry-run) DRY_RUN=1 ;;
    --force) FORCE=1 ;;
    --quiet) QUIET=1 ;;
    -h|--help) usage; exit $EXIT_OK ;;
    *) err "unknown option: $1"; usage; exit $EXIT_USAGE ;;
  esac
  shift
done

case "$TARGET" in
  personal|project) ;;
  *) die $EXIT_USAGE "--target must be 'personal' or 'project', got '$TARGET'" ;;
esac

# --------------------------------------------------------------------------
# Source checkout
# --------------------------------------------------------------------------

resolve_source() {
  if [ -n "$SOURCE_DIR" ]; then
    [ -d "$SOURCE_DIR/skills" ] || die $EXIT_INPUT \
      "--source '$SOURCE_DIR' has no skills/ directory"
    SOURCE_DIR=$(cd "$SOURCE_DIR" && pwd)
    log "source: $SOURCE_DIR (local)"
    return
  fi

  # Running from inside a checkout is the common case for contributors.
  script_dir=$(cd "$(dirname "$0")" && pwd)
  if [ -d "$script_dir/skills" ] && [ -f "$script_dir/install.sh" ]; then
    SOURCE_DIR="$script_dir"
    log "source: $SOURCE_DIR (this checkout)"
    return
  fi

  command -v git >/dev/null 2>&1 || die $EXIT_INPUT \
    "git is required to fetch $REPO_URL. Install git, or pass --source with a local checkout."

  mkdir -p "$CACHE_DIR"
  if [ -d "$CACHE_DIR/repo/.git" ]; then
    log "updating cache: $CACHE_DIR/repo"
    if [ "$DRY_RUN" -eq 0 ]; then
      git -C "$CACHE_DIR/repo" fetch --quiet --depth 1 origin "$REPO_REF" ||
        die $EXIT_INPUT "could not fetch '$REPO_REF' from $REPO_URL"
      git -C "$CACHE_DIR/repo" checkout --quiet FETCH_HEAD
    fi
  else
    log "cloning $REPO_URL@$REPO_REF into $CACHE_DIR/repo"
    if [ "$DRY_RUN" -eq 0 ]; then
      git clone --quiet --depth 1 --branch "$REPO_REF" "$REPO_URL" "$CACHE_DIR/repo" ||
        die $EXIT_INPUT "could not clone $REPO_URL at ref '$REPO_REF'"
    fi
  fi
  SOURCE_DIR="$CACHE_DIR/repo"
  [ -d "$SOURCE_DIR/skills" ] || die $EXIT_MALFORMED \
    "the checkout at $SOURCE_DIR has no skills/ directory"
}

# --------------------------------------------------------------------------
# Skill discovery. Frontmatter is read with sed; no YAML parser needed for the
# two fields the installer cares about.
# --------------------------------------------------------------------------

list_skill_paths() {
  for layer in utilities knowledge patterns processes; do
    [ -d "$SOURCE_DIR/skills/$layer" ] || continue
    for dir in "$SOURCE_DIR/skills/$layer"/*/; do
      [ -f "$dir/SKILL.md" ] || continue
      printf '%s\n' "${dir%/}"
    done
  done
}

frontmatter_field() {
  # $1 = SKILL.md path, $2 = field name. Returns the first line's value only,
  # which is all the installer needs (name, maturity).
  sed -n '/^---$/,/^---$/p' "$1" |
    sed -n "s/^[[:space:]]*$2:[[:space:]]*//p" |
    head -n 1 |
    sed 's/^["'"'"']//; s/["'"'"']$//'
}

do_list() {
  printf '%-30s %-11s %-11s %s\n' "SKILL" "LAYER" "MATURITY" "OWNER"
  list_skill_paths | while IFS= read -r dir; do
    name=$(basename "$dir")
    layer=$(basename "$(dirname "$dir")")
    maturity=$(frontmatter_field "$dir/SKILL.md" "maturity")
    owner=$(frontmatter_field "$dir/SKILL.md" "owner")
    printf '%-30s %-11s %-11s %s\n' "$name" "$layer" "${maturity:-?}" "${owner:-?}"
  done
}

# --------------------------------------------------------------------------
# Destinations
# --------------------------------------------------------------------------

detect_harnesses() {
  detected=""
  [ -d "$HOME/.claude" ] || [ -d ".claude" ] && detected="$detected claude"
  [ -d "$HOME/.cursor" ] || [ -d ".cursor" ] && detected="$detected cursor"
  [ -d "$HOME/.agents" ] || [ -d ".agents" ] && detected="$detected agents"
  [ -d ".github" ] && [ "$TARGET" = "project" ] && detected="$detected copilot"
  printf '%s' "$detected"
}

destination_for() {
  case "$1:$TARGET" in
    claude:personal)  printf '%s' "$HOME/.claude/skills" ;;
    claude:project)   printf '%s' ".claude/skills" ;;
    cursor:personal)  printf '%s' "$HOME/.cursor/skills" ;;
    cursor:project)   printf '%s' ".cursor/skills" ;;
    agents:personal|codex:personal) printf '%s' "$HOME/.agents/skills" ;;
    agents:project|codex:project)   printf '%s' ".agents/skills" ;;
    copilot:personal) printf '%s' "" ;;
    copilot:project)  printf '%s' ".github/skills" ;;
    *) printf '%s' "" ;;
  esac
}

# --------------------------------------------------------------------------
# Local-modification detection
# --------------------------------------------------------------------------

# Decided once. `shasum` is preferred for fewer collisions; `cksum` is POSIX and
# present everywhere, so there is always a fallback.
if command -v shasum >/dev/null 2>&1; then
  HASHER="shasum -a 256"
else
  HASHER="cksum"
fi

# shellcheck disable=SC2086  # $HASHER is a command plus its flags; it must split.
tree_checksum() {
  # A stable checksum over file contents and relative paths.
  #
  # No `find -print0` and no `read -d ''`: both are bashisms. They work on macOS,
  # where /bin/sh is bash in POSIX mode, and fail on dash, where /bin/sh usually
  # is on Linux -- silently, taking local-modification detection with them.
  # Hashing in a single `find -exec` avoids the read loop entirely.
  #
  dir="$1"
  ( cd "$dir" 2>/dev/null &&
      find . -type f ! -name "$STAMP_FILE" -exec $HASHER {} + 2>/dev/null |
      LC_ALL=C sort ) | $HASHER | cut -d' ' -f1
}

# --------------------------------------------------------------------------
# Install
# --------------------------------------------------------------------------

install_one() {
  src="$1"; dest_root="$2"; name=$(basename "$src")
  dest="$dest_root/$name"

  if [ -d "$dest" ]; then
    recorded=""
    [ -f "$dest/$STAMP_FILE" ] && recorded=$(sed -n 's/^checksum=//p' "$dest/$STAMP_FILE" | head -n 1)
    current=$(tree_checksum "$dest")
    if [ -n "$recorded" ] && [ "$recorded" != "$current" ] && [ "$FORCE" -eq 0 ]; then
      warn "$name at $dest has local modifications; skipping. Use --force to overwrite."
      : > "$REFUSED_MARKER"
      return 0
    fi
    if [ -z "$recorded" ] && [ "$FORCE" -eq 0 ]; then
      warn "$name at $dest was not installed by this script; skipping. Use --force to overwrite."
      : > "$REFUSED_MARKER"
      return 0
    fi
  fi

  if [ "$DRY_RUN" -eq 1 ]; then
    log "would install $name -> $dest"
    return 0
  fi

  mkdir -p "$dest_root"
  rm -rf "$dest.crv-tmp"
  cp -R "$src" "$dest.crv-tmp"
  rm -rf "$dest"
  mv "$dest.crv-tmp" "$dest"

  checksum=$(tree_checksum "$dest")
  {
    printf 'source=%s\n' "$REPO_URL"
    printf 'ref=%s\n' "$REPO_REF"
    printf 'installed_at=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf 'checksum=%s\n' "$checksum"
    printf '# Written by install.sh. Editing this skill in place makes the checksum\n'
    printf '# disagree, which is how the installer knows not to clobber your change.\n'
  } > "$dest/$STAMP_FILE"

  log "installed $name -> $dest"
  : >> "$INSTALLED_MARKER"
  printf '.' >> "$INSTALLED_MARKER"
}

# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

resolve_source

if [ "$DO_LIST" -eq 1 ]; then
  do_list
  exit $EXIT_OK
fi

if [ "$WANT_ALL" -eq 0 ] && [ -z "$SELECTED" ]; then
  err "nothing selected. Pass --all, or --skill NAME (repeatable), or --list to see what exists."
  usage
  exit $EXIT_USAGE
fi

ALL_PATHS=$(list_skill_paths)
[ -n "$ALL_PATHS" ] || die $EXIT_MALFORMED "no skills found under $SOURCE_DIR/skills"

CHOSEN=""
if [ "$WANT_ALL" -eq 1 ]; then
  CHOSEN="$ALL_PATHS"
else
  for want in $SELECTED; do
    match=""
    for path in $ALL_PATHS; do
      [ "$(basename "$path")" = "$want" ] && match="$path"
    done
    [ -n "$match" ] || die $EXIT_INPUT "unknown skill '$want'. Run --list to see what exists."
    CHOSEN="$CHOSEN
$match"
  done
fi

if [ -n "$EXPLICIT_DIR" ]; then
  DESTINATIONS="$EXPLICIT_DIR"
else
  [ -n "$HARNESSES" ] || HARNESSES=$(detect_harnesses | tr ' ' ',')
  HARNESSES=$(printf '%s' "$HARNESSES" | sed 's/^,*//; s/,,*/,/g')
  [ -n "$HARNESSES" ] || die $EXIT_INPUT \
    "no harness detected. Pass --harness claude,cursor,copilot,codex,agents or --dir PATH."
  DESTINATIONS=""
  old_ifs=$IFS; IFS=','
  for harness in $HARNESSES; do
    IFS=$old_ifs
    dest=$(destination_for "$harness")
    if [ -z "$dest" ]; then
      warn "$harness has no $TARGET install location; skipping."
      IFS=','
      continue
    fi
    DESTINATIONS="$DESTINATIONS
$dest"
    IFS=','
  done
  IFS=$old_ifs
fi

[ -n "$(printf '%s' "$DESTINATIONS" | tr -d '[:space:]')" ] ||
  die $EXIT_INPUT "no usable destination for target '$TARGET'"

# The install loop below runs inside a pipeline, which shells run in a subshell:
# a counter incremented there is lost when the subshell exits. Marker files
# survive it, so the exit code reflects what actually happened.
WORK_DIR=$(mktemp -d 2>/dev/null || printf '%s' "${TMPDIR:-/tmp}/crv-install.$$")
mkdir -p "$WORK_DIR"
REFUSED_MARKER="$WORK_DIR/refused"
INSTALLED_MARKER="$WORK_DIR/installed"
: > "$INSTALLED_MARKER"
trap 'rm -rf "$WORK_DIR"' EXIT INT TERM

printf '%s\n' "$DESTINATIONS" | while IFS= read -r dest_root; do
  [ -n "$dest_root" ] || continue
  log "destination: $dest_root"
  printf '%s\n' "$CHOSEN" | while IFS= read -r src; do
    [ -n "$src" ] || continue
    install_one "$src" "$dest_root"
  done
done

if [ "$DRY_RUN" -eq 1 ]; then
  log "dry run: nothing was written. Re-run without --dry-run to install."
else
  installed_count=$(wc -c < "$INSTALLED_MARKER" | tr -d ' ')
  log "installed $installed_count skill copy(ies)."
fi

if [ -f "$REFUSED_MARKER" ]; then
  err "one or more skills were skipped because they had local changes. Re-run with --force to overwrite them."
  exit $EXIT_REFUSED
fi

exit $EXIT_OK
