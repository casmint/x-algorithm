# Bootstrap Census Correction

During Phase 1B validation, one issue in the initial Phase 1A census was found and corrected before deep review began.

`media-model-proxy/src/test/resources/test_decider_base.yml` is a **Git symlink** to `../../../config/decider.yml`.

The initial bootstrap's Git-tree verification was still correct, because the tree reconstruction used the archive's Git mode and symlink object. However, the first `file_manifest.csv` census row dereferenced the symlink when calculating size/hash/line metadata, so it duplicated the target file's 2,056 bytes and 59 lines.

The corrected snapshot now records:

- Git mode: `120777`
- symlink object bytes: `../../../config/decider.yml`
- symlink object size: 27 bytes
- symlink-object SHA-256: `c4586656f0a1d4ca1074f0b63eca1898bcfe4b00f7760a5f9b55caf054145de1`
- Git blob SHA-1: `6fed3ecee161459174d5a065e9dc297405b2806c`

Corrected census totals are **13,452,561 Git-object bytes**, **2,014 UTF-8 regular text files**, **379,995 approximate regular-text lines**, and **1 symlink**.

This correction changes no upstream source and no algorithm conclusion; no behavioral review had begun. The Phase 1B package supersedes the original bootstrap package.
