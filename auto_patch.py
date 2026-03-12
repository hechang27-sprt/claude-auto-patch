#!/usr/bin/env python3
"""
Claude Code auto-patch engine

Config: auto-patch-config.json (same directory)
Cache:  ~/.claude/.auto-patch-cache.json

Called by the shell wrapper installed via install.py.

To add a new patch:
  1. Add a PatchDef entry to the PATCHES dict
  2. Add the toggle to auto-patch-config.json
"""

import json
import os
import re
import shutil
import platform
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

# -- Platform constants -------------------------------------------------------

SYSTEM = platform.system()
IS_WINDOWS = (
    SYSTEM == "Windows"
    or "MSYS" in os.environ.get("MSYSTEM", "")
    or "MINGW" in platform.platform()
)

BACKUP_SUFFIX = ".autopatch-bak"
SCRIPT_DIR = Path(__file__).parent
CONFIG_FILE = SCRIPT_DIR / "auto-patch-config.json"
CACHE_FILE = Path.home() / ".claude" / ".auto-patch-cache.json"


# -- Patch definition framework -----------------------------------------------

@dataclass
class PatchDef:
    """Single patch definition.

    Attributes:
        name:              Unique patch identifier (matches config key)
        description:       What this patch does
        target_re:         Regex matching unpatched code (full match = replacement span)
        patched_re:        Regex matching patched code (for status detection)
        build_replacement: Takes a re.Match, returns equal-length replacement bytes
        target_type:       "bun" (binary), "npm" (JS file), or "all"
    """
    name: str
    description: str
    target_re: re.Pattern[bytes]
    patched_re: re.Pattern[bytes]
    build_replacement: Callable[[re.Match[bytes]], bytes]
    target_type: str = "all"


def _equal_length_replace(
    prefix: bytes, suffix: bytes, match: re.Match[bytes]
) -> bytes:
    """Generic equal-length replacement builder: prefix + space padding + suffix"""
    total = len(match.group(0))
    padding = total - len(prefix) - len(suffix)
    if padding < 0:
        raise ValueError(
            f"Replacement template ({len(prefix)+len(suffix)}B) "
            f"exceeds original ({total}B)"
        )
    return prefix + (b" " * padding) + suffix


# -- Patch definitions --------------------------------------------------------
# Each patch is a PatchDef instance.
# To add a new patch:
#   1. Define target_re (regex matching original code, tolerant of variable names)
#   2. Define patched_re (regex matching patched code, for status detection)
#   3. Define build_replacement (equal-length replacement logic)
#   4. Add toggle to auto-patch-config.json

PATCHES: dict[str, PatchDef] = {
    "toolsearch": PatchDef(
        name="toolsearch",
        description="Remove Tool Search domain restriction",
        # Matches: return["api.anthropic.com"].includes(<var>)}catch{return!1}
        # <var> is any JS identifier, may change between versions
        target_re=re.compile(
            rb'return\["api\.anthropic\.com"\]\.includes\('
            rb"([A-Za-z_$][A-Za-z0-9_$]*)"
            rb"\)\}catch\{return!1\}"
        ),
        # Matches: return!0/* ... */}catch{return!0}
        patched_re=re.compile(
            rb"return!0/\* *\*/\}catch\{return!0\}"
        ),
        build_replacement=lambda m: _equal_length_replace(
            b"return!0/*", b"*/}catch{return!0}", m
        ),
    ),

    # -- Add new patches here --
    # "example": PatchDef(
    #     name="example",
    #     description="Example patch description",
    #     target_re=re.compile(rb'original code regex'),
    #     patched_re=re.compile(rb'patched code regex'),
    #     build_replacement=lambda m: _equal_length_replace(
    #         b"prefix", b"suffix", m
    #     ),
    # ),
}


# -- Config loading ------------------------------------------------------------

def load_config() -> dict[str, bool]:
    """Load patch toggle config."""
    try:
        return json.loads(CONFIG_FILE.read_text("utf-8"))
    except Exception:
        return {name: True for name in PATCHES}


# -- Target detection ----------------------------------------------------------

@dataclass
class Target:
    """Patch target file."""
    path: Path
    kind: str  # "bun" or "npm"


def find_targets() -> list[Target]:
    """Find all files that need patching."""
    targets: list[Target] = []
    seen: set[str] = set()

    def _add(path: Path, kind: str):
        key = str(path)
        if key not in seen and path.is_file():
            seen.add(key)
            targets.append(Target(path, kind))

    # 1. Bun binary (find active claude in PATH)
    names = ["claude.exe", "claude.cmd", "claude"] if IS_WINDOWS else ["claude"]
    for dir_str in os.environ.get("PATH", "").split(os.pathsep):
        if not dir_str:
            continue
        d = Path(dir_str)
        for name in names:
            p = d / name
            if p.is_file():
                try:
                    resolved = p.resolve(strict=True)
                except OSError:
                    resolved = p
                try:
                    if resolved.stat().st_size > 10 * 1024 * 1024:
                        _add(resolved, "bun")
                except OSError:
                    pass
                break
        if targets:
            break

    # 2. npm global install
    npm_root = _run_cmd(["npm", "root", "-g"])
    if npm_root:
        _find_npm_target(Path(npm_root), targets, seen)

    return targets


def _find_npm_target(
    npm_root: Path, targets: list[Target], seen: set[str]
):
    pkg_dir = npm_root / "@anthropic-ai" / "claude-code"
    if not pkg_dir.is_dir():
        return
    cli_js = pkg_dir / "cli.js"
    if cli_js.is_file():
        try:
            if b"api.anthropic.com" in cli_js.read_bytes():
                key = str(cli_js)
                if key not in seen:
                    seen.add(key)
                    targets.append(Target(cli_js, "npm"))
                return
        except OSError:
            pass
    for js_file in sorted(pkg_dir.rglob("*.js")):
        try:
            if js_file.stat().st_size < 1000:
                continue
            if b"api.anthropic.com" in js_file.read_bytes():
                key = str(js_file)
                if key not in seen:
                    seen.add(key)
                    targets.append(Target(js_file, "npm"))
                return
        except OSError:
            continue


def _run_cmd(cmd: list[str], fallback: str = "") -> str:
    if not shutil.which(cmd[0]):
        return fallback
    try:
        kw: dict = {}
        if IS_WINDOWS:
            kw["creationflags"] = subprocess.CREATE_NO_WINDOW
            kw["shell"] = True
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=5, **kw)
        return r.stdout.strip() if r.returncode == 0 else fallback
    except Exception:
        return fallback


# -- Cache ---------------------------------------------------------------------
# Structure: { "<file_path>": { "mtime": float, "patches": ["toolsearch", ...] } }

def _load_cache() -> dict:
    try:
        return json.loads(CACHE_FILE.read_text("utf-8"))
    except Exception:
        return {}


def _save_cache(cache: dict):
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(json.dumps(cache, indent=2), "utf-8")
    except OSError:
        pass


def _needs_check(
    target: Path, enabled_patches: list[str], cache: dict
) -> bool:
    """Check if re-scan is needed: file changed or enabled patches changed."""
    key = str(target)
    entry = cache.get(key)
    if not entry:
        return True
    try:
        mtime = target.stat().st_mtime
    except OSError:
        return True
    if entry.get("mtime") != mtime:
        return True
    if sorted(entry.get("patches", [])) != sorted(enabled_patches):
        return True
    return False


# -- Patch application ---------------------------------------------------------

def _get_patch_status(data: bytes, patch: PatchDef) -> str:
    if patch.target_re.search(data):
        return "unpatched"
    if patch.patched_re.search(data):
        return "patched"
    return "unknown"


def _apply_patches(
    target: Target, patches: list[PatchDef]
) -> tuple[bytes, list[str], list[str]]:
    """Apply multiple patches to file data.

    Returns: (patched_data, applied_names, skipped_names)
    """
    data = target.path.read_bytes()
    applied: list[str] = []
    skipped: list[str] = []

    for patch in patches:
        if patch.target_type not in ("all", target.kind):
            continue

        status = _get_patch_status(data, patch)

        if status == "patched":
            skipped.append(patch.name)
            continue

        if status == "unknown":
            continue

        count = 0

        def replace(m: re.Match[bytes]) -> bytes:
            nonlocal count
            count += 1
            return patch.build_replacement(m)

        data = patch.target_re.sub(replace, data)
        if count > 0:
            applied.append(patch.name)

    return data, applied, skipped


def _write_patched(target: Path, data: bytes) -> tuple[bool, str]:
    """Write patched data, handling file-in-use scenarios."""
    try:
        target.write_bytes(data)
        return True, "direct write"
    except PermissionError:
        pass

    # File in use (Windows running exe) - use rename strategy
    tmp_path = target.with_suffix(target.suffix + ".tmp")
    old_path = target.with_suffix(target.suffix + ".old")
    try:
        if tmp_path.exists():
            tmp_path.unlink()
        tmp_path.write_bytes(data)
        os.replace(target, old_path)
        os.replace(tmp_path, target)
        try:
            old_path.unlink()
        except OSError:
            pass
        return True, "rename swap"
    except OSError as e:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        return False, str(e)


def _resign_if_needed(path: Path):
    """Ad-hoc re-sign modified binary on macOS."""
    if SYSTEM != "Darwin":
        return
    try:
        subprocess.run(
            ["codesign", "--force", "--sign", "-", str(path)],
            capture_output=True, timeout=10,
        )
    except Exception:
        pass


# -- Main ----------------------------------------------------------------------

def main():
    config = load_config()
    enabled = [name for name, on in config.items() if on and name in PATCHES]
    if not enabled:
        return

    targets = find_targets()
    if not targets:
        return

    cache = _load_cache()
    messages: list[str] = []

    for target in targets:
        if not _needs_check(target.path, enabled, cache):
            continue

        patches_to_apply = [PATCHES[name] for name in enabled]

        try:
            patched_data, applied, skipped = _apply_patches(
                target, patches_to_apply
            )
        except OSError:
            continue

        if applied:
            backup = target.path.parent / (target.path.name + BACKUP_SUFFIX)
            try:
                shutil.copy2(target.path, backup)
            except OSError:
                continue

            ok, method = _write_patched(target.path, patched_data)
            if not ok:
                messages.append(
                    f"[auto-patch] {target.path.name} write failed: {method}\n"
                    f"  Hint: ensure no claude process is running, "
                    f"or re-run via the shell wrapper (python install.py)"
                )
                continue

            _resign_if_needed(target.path)

            patch_names = ", ".join(applied)
            messages.append(
                f"[auto-patch] {target.path.name}: "
                f"applied {patch_names} ({method})"
            )

        try:
            cache[str(target.path)] = {
                "mtime": target.path.stat().st_mtime,
                "patches": enabled,
            }
        except OSError:
            pass

    _save_cache(cache)

    # Output notifications
    for msg in messages:
        print(msg)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Must never crash Claude Code startup
        pass
