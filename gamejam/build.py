"""Page-specific build checks for gamejam.

The repository build entry (../build.py) imports this file when present:

    prebuild(ctx)   before page.toml's include list is copied
    postbuild(ctx)  after files are copied into the staging directory

This file is source-only and is never copied into dist/gamejam/.
"""

from __future__ import annotations

REQUIRED_RUNTIME = (
    "mirror-2610/index.html",
    "mirror-2610/content-field.js",
    "mirror-2610/data/ranking.json",
    "mirror-2610/data/works.json",
    "assets/mirror-26/cea-logo.svg",
    "js/effects/mirror.js",
    "js/effects/fade.js",
    "js/effects/parallax.js",
    "libs/three/three-bundle-loader.js",
    "libs/three/three.bundle.js",
    "libs/three/vendor/three.core.js",
    "libs/three/vendor/three.module.js",
)

# The minified bundle is ~740 KiB. A much smaller file means the generated
# artifact was truncated or replaced with an error page.
MIN_BUNDLE_BYTES = 500_000

BUNDLE = "libs/three/three.bundle.js"
BUNDLE_ENTRY = "libs/three/src/three-bundle-entry.js"

# These must never leak into the deployed page.
FORBIDDEN_STAGE_PATHS = (
    "tools",
    "build.py",
    "page.toml",
    "mirror-2610/mirror-lab.html",
    ".gitignore",
    "libs/three/src",
    "libs/three/three-bundle-entry.js",
    "js/mirror.js",
    "js/three.bundle.js",
    "js/three-bundle-loader.js",
    "js/vendor",
    "js/__pycache__",
    "tools/__pycache__",
)


def prebuild(ctx) -> None:
    """Validate source files before the generic copy step."""
    missing = [
        relative
        for relative in REQUIRED_RUNTIME
        if not (ctx.source / relative).is_file()
    ]
    if missing:
        raise RuntimeError(
            "missing runtime files: " + ", ".join(sorted(missing))
        )

    bundle = ctx.source / BUNDLE
    if bundle.stat().st_size < MIN_BUNDLE_BYTES:
        raise RuntimeError(
            f"{BUNDLE} looks truncated ({bundle.stat().st_size} bytes); "
            "run tools/build-three-bundle.ps1"
        )

    entry_source = ctx.source / BUNDLE_ENTRY
    if entry_source.is_file() and bundle.stat().st_mtime + 60 < entry_source.stat().st_mtime:
        ctx.warn(
            f"{BUNDLE} is older than {BUNDLE_ENTRY}; "
            "run tools/build-three-bundle.ps1"
        )

    ctx.log(f"validated {len(REQUIRED_RUNTIME)} required runtime files")


def postbuild(ctx) -> None:
    """Guard the staging tree against leaking source-only files."""
    leaked = [
        relative
        for relative in FORBIDDEN_STAGE_PATHS
        if (ctx.stage / relative).exists()
    ]
    if leaked:
        raise RuntimeError(
            "source-only paths leaked into dist: " + ", ".join(sorted(leaked))
        )

    entry = ctx.stage / ctx.page.entry
    if not entry.is_file() or entry.stat().st_size == 0:
        raise RuntimeError(f"staged entry is missing or empty: {ctx.page.entry}")

    ctx.log("staging tree checked for source-only files")
