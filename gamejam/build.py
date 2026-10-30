"""Page-specific build checks for gamejam.

The repository build entry (../build.py) imports this file when present:

    prebuild(ctx)   before page.toml's include list is copied
    postbuild(ctx)  after files are copied into the staging directory

This file is source-only and is never copied into dist/gamejam/.
"""

from __future__ import annotations

REQUIRED_RUNTIME = (
    "js/mirror.js",
    "js/three-bundle-loader.js",
    "js/three.bundle.js",
    "js/vendor/three.core.js",
    "js/vendor/three.module.js",
)

# The minified bundle is ~740 KiB. A much smaller file means the generated
# artifact was truncated or replaced with an error page.
MIN_BUNDLE_BYTES = 500_000

# These must never leak into the deployed page.
FORBIDDEN_STAGE_PATHS = (
    "tools",
    "build.py",
    "page.toml",
    ".gitignore",
    "js/three-bundle-entry.js",
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

    bundle = ctx.source / "js" / "three.bundle.js"
    if bundle.stat().st_size < MIN_BUNDLE_BYTES:
        raise RuntimeError(
            f"js/three.bundle.js looks truncated ({bundle.stat().st_size} bytes); "
            "run tools/build-three-bundle.ps1"
        )

    entry_source = ctx.source / "js" / "three-bundle-entry.js"
    if entry_source.is_file() and bundle.stat().st_mtime + 60 < entry_source.stat().st_mtime:
        ctx.warn(
            "js/three.bundle.js is older than js/three-bundle-entry.js; "
            "run tools/build-three-bundle.ps1"
        )

    lab = ctx.source / "mirror-lab.html"
    if lab.is_file():
        lab_text = lab.read_text(encoding="utf-8")
        if "three-bundle-loader.js" not in lab_text:
            ctx.warn("mirror-lab.html no longer imports js/three-bundle-loader.js")

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
