# Patching Guide

## Bun Binary Structure

Claude Code's bun binary = native shell + embedded minified JS bundle.
The JS code is minified (short variable names, no whitespace) but string literals are preserved.
This is identical to the npm version's `cli.js` content.

## Equal-Length Replacement

The binary has fixed offsets. Changing byte length corrupts everything downstream.

### Technique: Comment Padding

```python
prefix = b'return!0/*'
suffix = b'*/}catch{return!0}'

def build_replacement(original_length):
    padding = original_length - len(prefix) - len(suffix)
    assert padding >= 0
    return prefix + (b' ' * padding) + suffix
```

### Common Replacement Patterns

| Original Pattern | Replacement | Effect |
|-----------------|-------------|--------|
| `return!1` | `return!0` | false -> true |
| `return!0` | `return!1` | true -> false |
| `if(check){action}` | `if(!1   ){action}` | Skip the action |
| `condition&&action` | `!1       &&action` | Disable action (pad with spaces) |

## Regex Design

### Tolerate Variable Name Changes

Minifiers rename variables each build. Never hardcode variable names:

```python
# Good: matches any JS identifier
rb'\.includes\(([A-Za-z_$][A-Za-z0-9_$]*)\)'

# Bad: hardcoded variable name
rb'\.includes\(Xe\)'
```

### Anchor on Stable Strings

String literals, property names, and structural patterns survive minification:

- `"api.anthropic.com"` - string literals
- `.includes(` - method calls
- `}catch{` - control flow structure
- `return!1` / `return!0` - boolean returns

### Regex Structure

```python
target_re = re.compile(
    rb'<stable_prefix>'
    rb'(<variable_part>)'
    rb'<stable_suffix>'
)
```

## Three-State Detection

Every patch needs two regexes:

1. `target_re` - matches unpatched code (the original)
2. `patched_re` - matches patched code (the replacement)

Status logic:
- `target_re` matches -> "unpatched" -> safe to apply
- `patched_re` matches -> "patched" -> skip
- Neither matches -> "unknown" -> **do not touch** (version incompatible)

## Platform Notes

### Windows
- Running `.exe` cannot be overwritten but CAN be renamed
- Use `os.replace()` (not `os.rename()`) to handle existing target files
- Flow: write tmp -> replace exe with old -> replace tmp with exe

### macOS
- Modified binaries need ad-hoc re-signing: `codesign --force --sign - <binary>`
- Without re-signing, Gatekeeper blocks execution

## Discovery Workflow

### Finding patch targets in cli.js

```bash
# Search for keywords with context
python search_target.py <cli.js> "keyword"

# Multiple keywords for broader search
python search_target.py <cli.js> "api.anthropic.com"
python search_target.py <cli.js> "isAllowedDomain"
```

### Formatting for analysis

```bash
cp cli.js /tmp/cli-formatted.js
npx prettier --write /tmp/cli-formatted.js
# Now read specific sections with line numbers
```

### Testing regex against the file

```bash
python validate_patch.py \
  --target-re '<regex>' \
  --file <cli.js>
```
