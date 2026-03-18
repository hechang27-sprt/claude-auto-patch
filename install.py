#!/usr/bin/env python3
"""
claude-auto-patch installer

Installs/uninstalls a shell wrapper that runs auto_patch.py before launching
the real claude binary. Works with PowerShell, Bash, and Zsh.

Usage:
    python install.py              # install
    python install.py --uninstall  # uninstall
    python install.py --status     # check status
    python install.py --dry-run    # preview changes
"""

import argparse
import os
import platform
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.resolve()
PATCH_SCRIPT = PROJECT_ROOT / "auto_patch.py"

MARKER_START = "# CLAUDE-AUTO-PATCH:START - managed by claude-auto-patch, do not edit"
MARKER_END = "# CLAUDE-AUTO-PATCH:END"

SYSTEM = platform.system()
IS_WINDOWS = SYSTEM == "Windows"

# ---------------------------------------------------------------------------
# Shell wrapper templates
# ---------------------------------------------------------------------------

PWSH_TEMPLATE = """\
# CLAUDE-AUTO-PATCH:START - managed by claude-auto-patch, do not edit
function claude {{
    if (-not (Get-Process -Name claude -ErrorAction SilentlyContinue)) {{
        $p = "{patch_script}"
        if (Test-Path $p) {{ python $p 2>$null }}
    }}
    $exe = (Get-Command claude -CommandType Application -ErrorAction SilentlyContinue |
            Select-Object -First 1).Source
    if ($exe) {{ & $exe @args }} else {{ Write-Error "claude not found in PATH" }}
}}
# CLAUDE-AUTO-PATCH:END"""

BASH_ZSH_TEMPLATE = """\
# CLAUDE-AUTO-PATCH:START - managed by claude-auto-patch, do not edit
claude() {{
    if ! pgrep -x claude > /dev/null 2>&1; then
        [ -f "{patch_script}" ] && python3 "{patch_script}" 2>/dev/null
    fi
    command claude "$@"
}}
# CLAUDE-AUTO-PATCH:END"""

FISH_TEMPLATE = """\
# CLAUDE-AUTO-PATCH:START - managed by claude-auto-patch, do not edit
function claude
    if not pgrep -x claude >/dev/null 2>&1
        set -l p "{patch_script}"
        if test -f $p
            python3 $p 2>/dev/null
        end
    end
    command claude $argv
end
# CLAUDE-AUTO-PATCH:END"""

# ---------------------------------------------------------------------------
# Shell detection
# ---------------------------------------------------------------------------

def _detect_shells() -> list[tuple[str, Path]]:
    """Detect available shells and their profile paths.

    Returns list of (shell_name, profile_path) tuples.
    """
    shells: list[tuple[str, Path]] = []

    # PowerShell (pwsh) — primary on Windows
    pwsh_profile = _get_pwsh_profile()
    if pwsh_profile:
        shells.append(("pwsh", pwsh_profile))

    # Bash
    home = Path.home()
    bashrc = home / ".bashrc"
    if bashrc.exists() or not IS_WINDOWS:
        shells.append(("bash", bashrc))

    # Zsh
    zshrc = home / ".zshrc"
    if zshrc.exists():
        shells.append(("zsh", zshrc))

    # Fish
    fish_config = home / ".config" / "fish" / "config.fish"
    if fish_config.exists() or (home / ".config" / "fish").exists():
        shells.append(("fish", fish_config))

    return shells


def _get_pwsh_profile() -> Path | None:
    """Get PowerShell profile path."""
    # Check $PROFILE env var first (set when running inside pwsh)
    profile_env = os.environ.get("PROFILE")
    if profile_env:
        return Path(profile_env)

    if IS_WINDOWS:
        # Standard location: ~/Documents/PowerShell/Microsoft.PowerShell_profile.ps1
        docs = Path.home() / "Documents" / "PowerShell"
        profile = docs / "Microsoft.PowerShell_profile.ps1"
        if docs.exists() or profile.exists():
            return profile

    return None


# ---------------------------------------------------------------------------
# Profile manipulation
# ---------------------------------------------------------------------------

_BLOCK_RE = re.compile(
    r"(?:\r?\n)*"
    + re.escape(MARKER_START)
    + r".*?"
    + re.escape(MARKER_END)
    + r"(?:\r?\n)*",
    re.DOTALL,
)


def _read_profile(path: Path) -> str:
    """Read profile content, returns empty string if file doesn't exist."""
    try:
        return path.read_text("utf-8")
    except FileNotFoundError:
        return ""
    except OSError as e:
        print(f"  Warning: cannot read {path}: {e}", file=sys.stderr)
        return ""


def _has_block(content: str) -> bool:
    """Check if the managed block is present."""
    return MARKER_START in content


def _remove_block(content: str) -> str:
    """Remove the managed block from content."""
    return _BLOCK_RE.sub("\n", content).strip() + "\n" if content.strip() else ""


def _build_block(shell: str) -> str:
    """Build the wrapper block for the given shell."""
    patch_path = str(PATCH_SCRIPT).replace("\\", "/")
    if shell == "pwsh":
        return PWSH_TEMPLATE.format(patch_script=patch_path)
    elif shell == "fish":
        return FISH_TEMPLATE.format(patch_script=patch_path)
    else:
        return BASH_ZSH_TEMPLATE.format(patch_script=patch_path)


def _inject_block(content: str, shell: str) -> str:
    """Inject or replace the managed block in profile content."""
    block = _build_block(shell)
    if _has_block(content):
        # Replace existing block
        return _BLOCK_RE.sub("\n" + block + "\n", content)
    else:
        # Append to end
        stripped = content.rstrip()
        if stripped:
            return stripped + "\n\n" + block + "\n"
        else:
            return block + "\n"


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_install(shells: list[tuple[str, Path]], dry_run: bool = False):
    """Install the shell wrapper into detected profiles."""
    if not shells:
        print("No supported shell profiles detected.")
        print("Manually add the wrapper to your shell profile.")
        return False

    if not PATCH_SCRIPT.exists():
        print(f"Error: {PATCH_SCRIPT} not found.", file=sys.stderr)
        return False

    success = False
    for shell, profile in shells:
        content = _read_profile(profile)
        new_content = _inject_block(content, shell)

        if content == new_content:
            print(f"  [{shell}] {profile} — already installed, no changes needed")
            success = True
            continue

        if dry_run:
            print(f"  [{shell}] {profile} — would inject:")
            print()
            for line in _build_block(shell).splitlines():
                print(f"    {line}")
            print()
            success = True
            continue

        try:
            profile.parent.mkdir(parents=True, exist_ok=True)
            profile.write_text(new_content, "utf-8")
            print(f"  [{shell}] {profile} — installed")
            success = True
        except OSError as e:
            print(f"  [{shell}] {profile} — failed: {e}", file=sys.stderr)

    return success


def cmd_uninstall(shells: list[tuple[str, Path]], dry_run: bool = False):
    """Remove the shell wrapper from detected profiles."""
    if not shells:
        print("No supported shell profiles detected.")
        return False

    any_found = False
    for shell, profile in shells:
        content = _read_profile(profile)
        if not _has_block(content):
            print(f"  [{shell}] {profile} — not installed, nothing to remove")
            continue

        any_found = True
        new_content = _remove_block(content)

        if dry_run:
            print(f"  [{shell}] {profile} — would remove managed block")
            continue

        try:
            profile.write_text(new_content, "utf-8")
            print(f"  [{shell}] {profile} — uninstalled")
        except OSError as e:
            print(f"  [{shell}] {profile} — failed: {e}", file=sys.stderr)

    if not any_found and not dry_run:
        print("  Not installed in any profile.")

    return True


def cmd_status(shells: list[tuple[str, Path]]):
    """Show installation status."""
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Patch script: {PATCH_SCRIPT} ({'exists' if PATCH_SCRIPT.exists() else 'MISSING'})")
    print()

    if not shells:
        print("No supported shell profiles detected.")
        return

    for shell, profile in shells:
        content = _read_profile(profile)
        installed = _has_block(content)
        status = "installed" if installed else "not installed"
        exists = "exists" if profile.exists() else "does not exist"
        print(f"  [{shell}] {profile} — {exists}, {status}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Install/uninstall claude-auto-patch shell wrapper"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--uninstall", action="store_true", help="Remove wrapper from shell profiles"
    )
    group.add_argument(
        "--status", action="store_true", help="Show installation status"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview changes without modifying files"
    )
    args = parser.parse_args()

    shells = _detect_shells()

    if args.status:
        cmd_status(shells)
    elif args.uninstall:
        print("Uninstalling claude-auto-patch wrapper...")
        cmd_uninstall(shells, dry_run=args.dry_run)
    else:
        print("Installing claude-auto-patch wrapper...")
        ok = cmd_install(shells, dry_run=args.dry_run)
        if ok and not args.dry_run:
            print()
            print("Done! Restart your shell for changes to take effect.")


if __name__ == "__main__":
    main()
