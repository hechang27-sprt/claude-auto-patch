---
name: create-patch
description: >
  Create binary patches for Claude Code's bun executable or npm cli.js.
  Use when user wants to: (1) bypass a specific check or restriction in Claude Code,
  (2) modify Claude Code behavior by patching its source, (3) create a new auto-patch
  rule. Triggers on: "/create-patch", "create a patch", "patch Claude Code to...",
  "bypass the ... check", "disable ... in Claude Code".
---

# Create Patch for Claude Code

Create equal-length binary patches for Claude Code's minified JS code (bun binary or npm cli.js).

## Workflow

### 1. Locate npm cli.js

Find the npm-installed `@anthropic-ai/claude-code` package for analysis (npm version is text-friendly, ideal for code exploration).

```
npm root -g  -->  <root>/node_modules/@anthropic-ai/claude-code/cli.js
```

If not found, ask the user:

> npm version of Claude Code is not installed. It is needed as a reference for code analysis. Install it with `npm install -g @anthropic-ai/claude-code`?

Proceed only after cli.js is available.

### 2. Search for target code

Run `scripts/search_target.py` to find relevant code snippets:

```bash
python scripts/search_target.py <cli.js-path> "<keyword>"
```

The script returns matching snippets with byte offsets and surrounding context.

If the user's description is vague, search for multiple related keywords. Common search strategies:
- Domain restrictions: search for the domain string (e.g., `api.anthropic.com`)
- Feature flags: search for the flag name
- Error messages: search for the error text
- API calls: search for endpoint paths

### 3. Analyze the code

The snippets are minified JS. Mentally expand them:

```
# Minified
return["api.anthropic.com"].includes(Xe)}catch{return!1}

# Expanded
try {
  return ["api.anthropic.com"].includes(Xe);
} catch {
  return !1;  // false
}
```

For complex snippets, optionally create a formatted copy for deeper analysis:

```bash
npx prettier --write <temp-copy.js>
```

Identify:
- **What the code does** (the check/restriction being enforced)
- **What the desired behavior is** (what the patch should change it to)
- **The minimal replacement** that achieves the goal

### 4. Design equal-length replacement

**Critical constraint: the replacement MUST be exactly the same byte length as the original.**

Use JS comments (`/* */`) to absorb extra bytes:

```
Original: return["api.anthropic.com"].includes(Xe)}catch{return!1}
Patched:  return!0/*                          */}catch{return!0}
          ^--- same length, valid JS, different behavior ---^
```

Run `scripts/validate_patch.py` to verify:

```bash
python scripts/validate_patch.py \
  --target-re 'return\["api\.anthropic\.com"\]\.includes\([A-Za-z_$][A-Za-z0-9_$]*\)\}catch\{return!1\}' \
  --patched-re 'return!0/\* *\*/\}catch\{return!0\}' \
  --replacement-prefix 'return!0/*' \
  --replacement-suffix '*/}catch{return!0}' \
  --file "<cli.js path>"
```

The script checks: regex matches, equal length, valid replacement.

### 5. Register the patch

Read the project's `hooks/auto-patch.py`, add a new `PatchDef` entry in the `PATCHES` dict:

```python
"patch_name": PatchDef(
    name="patch_name",
    description="Description of what this patch does",
    target_re=re.compile(rb'...'),
    patched_re=re.compile(rb'...'),
    build_replacement=lambda m: _equal_length_replace(
        b"prefix", b"suffix", m
    ),
),
```

Update `hooks/auto-patch-config.json` to add the new patch (default enabled):

```json
{
  "existing_patch": true,
  "patch_name": true
}
```

### 6. Test

Run the auto-patch hook to verify:

```bash
# Clear cache to force re-check
rm -f ~/.claude/.auto-patch-cache.json
python hooks/auto-patch.py
```

Expected output: `[auto-patch] claude.exe: applied patch_name`

## Rules

- **Never change byte length** - Use `/* */` comments for padding
- **Regex must tolerate variable name changes** - Use `[A-Za-z_$][A-Za-z0-9_$]*` for JS identifiers
- **Three-state detection** - Every patch needs `target_re` (unpatched), `patched_re` (patched), and implicit "unknown" (neither matches)
- **unknown = do not patch** - If neither regex matches, the version is incompatible; skip silently
- **Replacement must be valid JS** - Syntax errors crash Claude Code on startup

For detailed patching principles, see [references/patching-guide.md](references/patching-guide.md).
