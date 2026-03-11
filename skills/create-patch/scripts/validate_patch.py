#!/usr/bin/env python3
"""Validate a patch definition against a Claude Code cli.js file.

Checks:
  1. target_re matches in the file (unpatched code found)
  2. patched_re does NOT match (not already patched)
  3. Replacement is exactly the same byte length as original
  4. Replacement produces valid output that patched_re can detect

Usage:
    python validate_patch.py \
        --target-re 'regex_for_unpatched' \
        --patched-re 'regex_for_patched' \
        --replacement-prefix 'return!0/*' \
        --replacement-suffix '*/}catch{return!0}' \
        --file <cli.js path>
"""

import argparse
import re
import sys


def validate(
    file_path: str,
    target_re_str: str,
    patched_re_str: str,
    replacement_prefix: str,
    replacement_suffix: str,
):
    with open(file_path, "rb") as f:
        data = f.read()

    target_re = re.compile(target_re_str.encode("utf-8"))
    patched_re = re.compile(patched_re_str.encode("utf-8"))
    prefix = replacement_prefix.encode("utf-8")
    suffix = replacement_suffix.encode("utf-8")

    errors = []
    warnings = []

    # Check 1: target_re matches
    target_matches = list(target_re.finditer(data))
    if not target_matches:
        if patched_re.search(data):
            warnings.append("target_re: no match (file appears already patched)")
        else:
            errors.append("target_re: no match found - regex may be wrong or version incompatible")
    else:
        print(f"[OK] target_re: {len(target_matches)} match(es) found")
        for i, m in enumerate(target_matches):
            print(f"     Match {i+1}: offset {m.start():#x}, length {len(m.group())} bytes")
            print(f"     Content: {repr(m.group()[:100])}")

    # Check 2: patched_re should NOT match (not already patched)
    patched_matches = list(patched_re.finditer(data))
    if patched_matches:
        warnings.append(f"patched_re: {len(patched_matches)} match(es) found - file may already be patched")
    else:
        print(f"[OK] patched_re: no match (file is not yet patched)")

    # Check 3: Equal length replacement
    if target_matches:
        for i, m in enumerate(target_matches):
            original_len = len(m.group())
            padding = original_len - len(prefix) - len(suffix)

            if padding < 0:
                errors.append(
                    f"Match {i+1}: replacement template ({len(prefix)+len(suffix)}B) "
                    f"exceeds original ({original_len}B) by {-padding} bytes"
                )
            else:
                replacement = prefix + (b" " * padding) + suffix
                assert len(replacement) == original_len
                print(f"[OK] Match {i+1}: equal length ({original_len}B), padding={padding}B")

                # Check 4: Replacement should be detectable by patched_re
                if patched_re.search(replacement):
                    print(f"[OK] Match {i+1}: replacement detected by patched_re")
                else:
                    errors.append(
                        f"Match {i+1}: patched_re does NOT match the replacement output. "
                        f"Replacement: {repr(replacement)}"
                    )

                # Show the replacement
                print(f"     Original:    {repr(m.group()[:100])}")
                print(f"     Replacement: {repr(replacement[:100])}")

    # Summary
    print()
    if errors:
        print(f"FAILED: {len(errors)} error(s)")
        for e in errors:
            print(f"  [ERROR] {e}")
        sys.exit(1)
    elif warnings:
        print(f"PASSED with {len(warnings)} warning(s)")
        for w in warnings:
            print(f"  [WARN] {w}")
    else:
        print("PASSED: all checks OK")


def main():
    parser = argparse.ArgumentParser(description="Validate a patch definition")
    parser.add_argument("--target-re", required=True, help="Regex matching unpatched code")
    parser.add_argument("--patched-re", required=True, help="Regex matching patched code")
    parser.add_argument("--replacement-prefix", required=True, help="Replacement prefix bytes")
    parser.add_argument("--replacement-suffix", required=True, help="Replacement suffix bytes")
    parser.add_argument("--file", required=True, help="Path to cli.js or binary")
    args = parser.parse_args()

    validate(
        args.file,
        args.target_re,
        args.patched_re,
        args.replacement_prefix,
        args.replacement_suffix,
    )


if __name__ == "__main__":
    main()
