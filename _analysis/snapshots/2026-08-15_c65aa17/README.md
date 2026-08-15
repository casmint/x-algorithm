# Snapshot: 2026-08-15 / c65aa17

This directory freezes the evidence base for the first full audit of `xai-org/x-algorithm`.

## Identity

- Upstream repository: `xai-org/x-algorithm`
- Upstream branch at capture: `main`
- Commit: `c65aa179db7bdd61e2c2821eac87f208a105c053`
- Commit time: `2026-08-14T20:55:37Z`
- Upstream Git tree: `1d4c89941bfcd2ea3aab7c780f7447342e304e42`
- Reconstructed tree from the supplied ZIP: `1d4c89941bfcd2ea3aab7c780f7447342e304e42`
- **Tree match: VERIFIED**
- Uploaded ZIP SHA-256: `8aa4dcb51127236cea4482460e35b5bf73e3eb7f5286720b997365cb5192c1e8`

The ZIP itself contains no `.git` directory. To verify it anyway, its files and Unix modes were loaded into a temporary Git index and `git write-tree` was run. The resulting tree object exactly matched the tree referenced by the public upstream commit.

## Census

- Files: **2,016**
- Top-level directories: **25**
- Uncompressed Git-object bytes: **13,452,561**
- UTF-8 regular text files: **2,014**
- Approximate regular-text lines: **379,995**

Largest source families by line count are recorded in `extension_census.csv`; per-component coverage is in `component_census.csv`.

## Files

- `snapshot.json` — machine-readable snapshot identity.
- `file_manifest.csv` — every file, size, line count, SHA-256, Git blob SHA, and indexing hints.
- `component_census.csv` — file/line/size totals by top-level component.
- `extension_census.csv` — totals by extension.
- `largest_files.csv` — top 50 largest files.
- `file_tree.txt` — complete path list.

The archive contains **1 Git symlink** (`media-model-proxy/src/test/resources/test_decider_base.yml` -> `../../../config/decider.yml`); census values count the symlink object itself rather than dereferencing it.

No behavioral conclusions belong in this snapshot directory. It exists so every later claim can be tied back to a fixed evidence set.
