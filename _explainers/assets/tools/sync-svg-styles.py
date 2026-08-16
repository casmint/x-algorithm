#!/usr/bin/env python3
"""Field Atlas SVG style synchronizer.

Every managed SVG in ../src stays self-contained (see ../README.md, "Why
each SVG is self-contained") — it never <link>s ../field-atlas.css at render
time. Instead, this script copies the canonical shared region of
field-atlas.css (design tokens + cross-cutting base rules, delimited by the
"SVG-SHARED BEGIN/END" markers in that file) into a clearly-marked, generated
<style id="field-atlas-shared"> block inside each managed SVG.

A SVG "opts in" to being managed simply by containing a
<style id="field-atlas-shared"> ... </style> block anywhere in the file —
no manifest to maintain. Diagram-specific CSS belongs in a separate,
hand-authored <style id="diagram-local-styles"> block, which this script
never touches.

Usage:
    python3 sync-svg-styles.py            # update stale generated blocks
    python3 sync-svg-styles.py --check    # report staleness, exit nonzero if any

Both modes are deterministic: given the same field-atlas.css and the same
set of managed SVGs, running sync twice in a row produces no second diff.

Standard library only — no dependencies.
"""

import argparse
import hashlib
import pathlib
import re
import sys

TOOLS_DIR = pathlib.Path(__file__).resolve().parent
ASSETS_DIR = TOOLS_DIR.parent
CSS_PATH = ASSETS_DIR / "field-atlas.css"
SRC_DIR = ASSETS_DIR / "src"

SHARED_BEGIN_MARKER = "/* === SVG-SHARED BEGIN === */"
SHARED_END_MARKER = "/* === SVG-SHARED END === */"

MANAGED_STYLE_ID = "field-atlas-shared"

# Matches: <style id="field-atlas-shared">\n ...generated content... \n  </style>
# Captures the opening tag+newline (group 1), the inner content (group 2), and
# the trailing newline+closing tag (group 3), so replacement can preserve
# whatever indentation the file already uses around the block.
STYLE_BLOCK_RE = re.compile(
    r'(<style id="' + re.escape(MANAGED_STYLE_ID) + r'">\n)(.*?)(\n[ \t]*</style>)',
    re.DOTALL,
)


def extract_shared_css() -> str:
    """Read field-atlas.css and return the text between the SVG-SHARED markers."""
    if not CSS_PATH.exists():
        sys.exit(f"error: canonical stylesheet not found: {CSS_PATH}")
    text = CSS_PATH.read_text()
    try:
        start = text.index(SHARED_BEGIN_MARKER) + len(SHARED_BEGIN_MARKER)
        end = text.index(SHARED_END_MARKER, start)
    except ValueError:
        sys.exit(
            f"error: {CSS_PATH} is missing the SVG-SHARED BEGIN/END markers "
            "— cannot determine what to inject"
        )
    return text[start:end].strip("\n")


def build_generated_block(shared_css: str) -> str:
    """Wrap the canonical shared CSS in DO-NOT-EDIT markers plus a provenance
    hash, indented to match the surrounding SVG's <style> formatting."""
    digest = hashlib.sha256(shared_css.encode("utf-8")).hexdigest()[:16]
    header = [
        "/* BEGIN GENERATED FIELD ATLAS CSS — DO NOT EDIT BY HAND */",
        "/*",
        "   Generated from ../field-atlas.css by tools/sync-svg-styles.py.",
        "   Run that script again after changing shared tokens in field-atlas.css.",
        f"   Source SHA256 (shared region, first 16 hex chars): {digest}",
        "*/",
    ]
    footer = ["/* END GENERATED FIELD ATLAS CSS */"]
    body_lines = header + shared_css.splitlines() + footer
    return "\n".join(("    " + line if line else "") for line in body_lines)


def find_managed_svgs() -> list[pathlib.Path]:
    """Any src/*.svg containing the managed style-id marker participates
    automatically — no list to hand-maintain as D1-D3 add new files."""
    marker = f'<style id="{MANAGED_STYLE_ID}">'
    return sorted(p for p in SRC_DIR.glob("*.svg") if marker in p.read_text())


def sync(check: bool) -> int:
    shared_css = extract_shared_css()
    generated = build_generated_block(shared_css)

    managed = find_managed_svgs()
    if not managed:
        print(f"no managed SVGs found under {SRC_DIR} (none contain a "
              f'<style id="{MANAGED_STYLE_ID}"> block)')
        return 0

    stale, updated, unchanged = [], [], []

    for svg_path in managed:
        original = svg_path.read_text()
        match = STYLE_BLOCK_RE.search(original)
        if not match:
            sys.exit(
                f"error: {svg_path} contains the '{MANAGED_STYLE_ID}' marker "
                "but not a well-formed <style id=\"field-atlas-shared\">...</style> "
                "block — cannot sync safely"
            )

        if match.group(2) == generated:
            unchanged.append(svg_path)
            continue

        if check:
            stale.append(svg_path)
            continue

        new_text = (
            original[: match.start()]
            + match.group(1) + generated + match.group(3)
            + original[match.end():]
        )
        svg_path.write_text(new_text)
        updated.append(svg_path)

    def rel(p: pathlib.Path) -> str:
        return str(p.relative_to(ASSETS_DIR))

    if check:
        for p in unchanged:
            print(f"OK     {rel(p)}")
        for p in stale:
            print(f"STALE  {rel(p)}")
        if stale:
            print(
                f"\n{len(stale)} of {len(managed)} managed SVG(s) out of sync "
                "with field-atlas.css — run: python3 tools/sync-svg-styles.py"
            )
            return 1
        print(f"\nall {len(unchanged)} managed SVG(s) in sync with field-atlas.css")
        return 0

    for p in unchanged:
        print(f"unchanged  {rel(p)}")
    for p in updated:
        print(f"updated    {rel(p)}")
    print(f"\n{len(updated)} updated, {len(unchanged)} already current "
          f"({len(managed)} managed total)")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync canonical Field Atlas CSS tokens into every managed SVG's "
                     "generated style block."
    )
    parser.add_argument(
        "--check", action="store_true",
        help="make no changes; report which managed SVGs are stale; "
             "exit nonzero if any are out of sync",
    )
    args = parser.parse_args()
    sys.exit(sync(check=args.check))


if __name__ == "__main__":
    main()
