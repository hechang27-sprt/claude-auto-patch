# claude-auto-patch

A configurable auto-patch system for [Claude Code](https://docs.anthropic.com/en/docs/claude-code). Automatically applies binary patches on session startup and survives updates.

## Features

- **Auto-patch on startup** - SessionStart hook detects updates and re-applies patches automatically
- **Configurable** - Enable/disable individual patches via JSON config
- **Smart caching** - Skips re-scanning unchanged binaries (uses file mtime)
- **Cross-platform** - Windows (rename-swap for running exe), macOS (codesign), Linux
- **Create patches with AI** - `/create-patch` skill guides Claude through the entire patch creation workflow

## Quick Start

### 1. Clone

```bash
git clone https://github.com/Cedriccmh/claude-auto-patch.git
```

### 2. Install Hook

Copy the hook files to your Claude Code hooks directory:

```bash
# Copy hook files
cp hooks/auto-patch.py ~/.claude/hooks/
cp hooks/auto-patch-config.json ~/.claude/hooks/
```

Add the SessionStart hook to your `~/.claude/settings.json`:

```jsonc
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup",
        "hooks": [
          {
            "type": "command",
            // Adjust path to where you placed auto-patch.py
            "command": "python ~/.claude/hooks/auto-patch.py"
          }
        ]
      }
    ]
  }
}
```

### 3. Install Skill (Optional)

To use the `/create-patch` skill for AI-assisted patch creation:

```bash
# Copy the skill to your Claude Code skills directory
cp -r skills/create-patch ~/.claude/skills/
```

Or install as a plugin by adding this repo path to your Claude Code configuration.

## Configuration

Edit `auto-patch-config.json` to toggle patches:

```json
{
  "toolsearch": true
}
```

Set a patch to `false` to disable it. Remove the cache file to force re-evaluation:

```bash
rm ~/.claude/.auto-patch-cache.json
```

## Built-in Patches

| Patch | Description | Default |
|-------|-------------|---------|
| `toolsearch` | Remove Tool Search domain restriction | Enabled |

## Creating New Patches

### Using the Skill (Recommended)

Use `/create-patch` in Claude Code and describe what you want to patch. The AI will:

1. Search the npm version of `cli.js` for relevant code
2. Analyze the minified JavaScript logic
3. Design an equal-length binary replacement
4. Register the patch definition and update config
5. Test the patch

### Manual

Add a `PatchDef` to `hooks/auto-patch.py`:

```python
"your_patch": PatchDef(
    name="your_patch",
    description="What this patch does",
    target_re=re.compile(rb'regex matching original code'),
    patched_re=re.compile(rb'regex matching patched code'),
    build_replacement=lambda m: _equal_length_replace(
        b"replacement_prefix", b"replacement_suffix", m
    ),
),
```

Then add the toggle to `auto-patch-config.json`:

```json
{
  "toolsearch": true,
  "your_patch": true
}
```

## How It Works

### Auto-Patch Flow

```
Claude Code starts
  -> SessionStart hook triggers
  -> Load config (which patches are enabled)
  -> Find claude binary / cli.js in PATH
  -> Check cache (file mtime + enabled patches)
  -> If unchanged: skip (< 1ms)
  -> If changed: read file, check each patch status
  -> Apply unpatched patches (equal-length byte replacement)
  -> Backup original, write patched version
  -> Update cache
```

### Equal-Length Replacement

Patches must be exactly the same byte length as the original code. This is achieved by using JavaScript comments (`/* */`) as padding:

```
Original: return["api.anthropic.com"].includes(Xe)}catch{return!1}
Patched:  return!0/*                          */}catch{return!0}
```

### Three-State Detection

Each patch has two regexes:
- `target_re` matches unpatched code -> safe to apply
- `patched_re` matches patched code -> already done, skip
- Neither matches -> version incompatible, do not touch

## Requirements

- Python 3.10+
- Claude Code (bun binary or npm install)

## License

MIT
