# amuxhq/buck2-prelude: tools

This branch holds no prelude. The prelude branches are `amux/<buck2 release>`:
Meta's mirror at that release's commit, plus one patch that gives the Android
toolchain's downloads a SHA-256 and a size, so a build cache keyed by SHA-256
can serve them instead of their origin.

`tools/inline_digests.py PRELUDE_DIR --fetch` writes `sha256` and
`size_bytes` (`oss_sha256` and `oss_size_bytes` for `buck_prebuilt_artifact`)
beside every SHA-1 in `toolchains/android` that lacks them, downloading each such file once and
checking it against its SHA-1. After rebasing the patch onto a new
release, run it to cover jars the release added.
