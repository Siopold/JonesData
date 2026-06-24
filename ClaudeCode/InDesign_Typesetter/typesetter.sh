#!/usr/bin/env bash
# typesetter.sh — auto-finds a Python with working Tkinter and launches the app.
#
# Why this exists: macOS ships Python builds whose bundled Tk version sometimes
# mismatches the OS build number and hard-aborts at runtime. Homebrew's
# python-tk formula fixes that by supplying a matching Tk extension module that
# lives outside the Python prefix (in Cellar/python-tk@X.Y/.../libexec), so we
# have to wire PYTHONPATH to point at it.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP="$SCRIPT_DIR/typesetter_app.py"

TK_TEST='import sys, tkinter; r = tkinter.Tk(); r.withdraw(); r.destroy()'

# Returns 0 if the given Python binary (plus optional extra PYTHONPATH prefix)
# can actually open a Tk window without crashing.
try_python() {
    local py="$1" extra="$2"
    [[ -x "$py" ]] || return 1
    PYTHONPATH="$extra" "$py" -c "$TK_TEST" 2>/dev/null
    return $?
}

FOUND_PY=""
FOUND_EXTRA=""

# ── 1. Homebrew python-tk pairings ───────────────────────────────────────────
# Intel Macs use /usr/local; Apple Silicon uses /opt/homebrew. Try both.
for brew_prefix in /usr/local /opt/homebrew; do
    [[ -d "$brew_prefix/Cellar" ]] || continue
    for ver in 3.13 3.12 3.11 3.10 3.9; do
        tk_base="${brew_prefix}/Cellar/python-tk@${ver}"
        py_base="${brew_prefix}/Cellar/python@${ver}"
        [[ -d "$tk_base" && -d "$py_base" ]] || continue

        libexec=$(find "$tk_base" -maxdepth 4 -name libexec -type d 2>/dev/null | head -1)
        py=$(find "$py_base" -maxdepth 8 -name "python${ver}" -type f 2>/dev/null | head -1)
        [[ -n "$libexec" && -n "$py" && -x "$py" ]] || continue

        if try_python "$py" "$libexec"; then
            FOUND_PY="$py"
            FOUND_EXTRA="$libexec"
            break 2
        fi
    done
done

# ── 2. Plain Python binaries (no extra PYTHONPATH needed) ────────────────────
if [[ -z "$FOUND_PY" ]]; then
    candidates=(
        /usr/bin/python3
        /usr/local/bin/python3
        /opt/homebrew/bin/python3
        "$HOME/miniconda3/bin/python3"
        "$HOME/miniforge3/bin/python3"
        "$HOME/anaconda3/bin/python3"
        "$HOME/.pyenv/shims/python3"
    )
    # Add whatever `python3` in PATH resolves to (avoids duplicates but that's fine)
    if command -v python3 &>/dev/null; then
        candidates+=("$(command -v python3)")
    fi

    for py in "${candidates[@]}"; do
        if try_python "$py" ""; then
            FOUND_PY="$py"
            break
        fi
    done
fi

# ── No working Python found ───────────────────────────────────────────────────
if [[ -z "$FOUND_PY" ]]; then
    msg="No Python with working Tkinter found.\n\nInstall one:\n  brew install python-tk@3.11\n\nThen re-run:\n  bash \"$0\""
    # Try to show a native macOS dialog; fall back to stderr
    osascript -e "display alert \"Baskerville Typesetter\" message \"$msg\" as critical" 2>/dev/null \
        || printf "ERROR: %b\n" "$msg" >&2
    exit 1
fi

# ── Launch ────────────────────────────────────────────────────────────────────
export PYTHONPATH="${FOUND_EXTRA}${PYTHONPATH:+:$PYTHONPATH}"
exec "$FOUND_PY" "$APP" "$@"
