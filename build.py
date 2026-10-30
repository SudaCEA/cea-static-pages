#!/usr/bin/env python3
"""Build static ellia-pages pages into dist/.

A page is a direct child directory containing page.toml. The manifest lists
the runtime files to copy; an optional build.py in that directory can add
pre-build checks and post-copy steps.

Usage:
    python build.py                  # build every page
    python build.py gamejam          # build one page
    python build.py gamejam other    # build selected pages
    python build.py --list           # show discovered pages
    python build.py --clean          # remove dist/ first
    python build.py --strict         # treat page warnings as errors
"""

from __future__ import annotations

import argparse
import fnmatch
import importlib.util
import re
import shutil
import sys
import time
import tomllib
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from types import ModuleType
from typing import Iterable

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Page hooks are imported from the source tree; do not leave __pycache__ there.
sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parent
DEFAULT_OUT = "dist"
MANIFEST_NAME = "page.toml"
PAGE_HOOK_NAME = "build.py"
SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class BuildError(RuntimeError):
    """A user-facing build failure."""


@dataclass(frozen=True)
class Page:
    slug: str
    source: Path
    title: str
    entry: str
    include: tuple[str, ...]
    exclude: tuple[str, ...]
    manifest_path: Path


@dataclass
class BuildContext:
    """Object passed to a page's optional build.py hooks."""

    page: Page
    stage: Path
    out_root: Path
    strict: bool
    verbose: bool
    warnings: list[str] = field(default_factory=list)

    @property
    def source(self) -> Path:
        """The page source directory, for convenience in page hooks."""
        return self.page.source

    def log(self, message: str) -> None:
        if self.verbose:
            print(f"  {message}")

    def warn(self, message: str) -> None:
        self.warnings.append(message)
        print(f"  [warn] {message}")


def _normalize_pattern(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BuildError(f"{label} must be a non-empty string")
    pattern = value.strip().replace("\\", "/")
    while pattern.startswith("./"):
        pattern = pattern[2:]
    pattern = pattern.rstrip("/") or "."
    if pattern.startswith("/") or re.match(r"^[A-Za-z]:", pattern):
        raise BuildError(f"{label} must be relative to the page: {value!r}")
    if ".." in PurePosixPath(pattern).parts:
        raise BuildError(f"{label} must not contain '..': {value!r}")
    return pattern


def _load_page(manifest_path: Path) -> Page:
    source = manifest_path.parent
    slug = source.name
    if not SLUG_RE.fullmatch(slug):
        raise BuildError(
            f"page directory name {slug!r} must use letters, digits, '.', '_' or '-'"
        )

    try:
        with manifest_path.open("rb") as handle:
            data = tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise BuildError(f"{manifest_path}: invalid TOML: {exc}") from exc
    except OSError as exc:
        raise BuildError(f"{manifest_path}: cannot read manifest: {exc}") from exc

    name = data.get("name", slug)
    if name != slug:
        raise BuildError(
            f"{manifest_path}: name = {name!r} must match the directory name {slug!r}"
        )

    title = data.get("title", slug)
    if not isinstance(title, str) or not title.strip():
        raise BuildError(f"{manifest_path}: title must be a non-empty string")

    entry = data.get("entry", "index.html")
    if not isinstance(entry, str):
        raise BuildError(f"{manifest_path}: entry must be a string")
    entry = _normalize_pattern(entry, f"{manifest_path}: entry")

    include_raw = data.get("include")
    if not isinstance(include_raw, list) or not include_raw:
        raise BuildError(
            f"{manifest_path}: include must be a non-empty array of file patterns"
        )
    include = tuple(
        _normalize_pattern(item, f"{manifest_path}: include[{index}]")
        for index, item in enumerate(include_raw)
    )

    exclude_raw = data.get("exclude", [])
    if not isinstance(exclude_raw, list):
        raise BuildError(f"{manifest_path}: exclude must be an array")
    exclude = tuple(
        _normalize_pattern(item, f"{manifest_path}: exclude[{index}]")
        for index, item in enumerate(exclude_raw)
    )

    return Page(
        slug=slug,
        source=source,
        title=title.strip(),
        entry=entry,
        include=include,
        exclude=exclude,
        manifest_path=manifest_path,
    )


def discover_pages(root: Path) -> list[Page]:
    pages: list[Page] = []
    for manifest in sorted(root.glob(f"*/{MANIFEST_NAME}")):
        if manifest.parent.name.startswith("."):
            continue
        pages.append(_load_page(manifest))
    return pages


def _is_excluded(relative_path: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatchcase(relative_path, pattern) for pattern in patterns)


def _collect_files(page: Page) -> dict[str, Path]:
    """Resolve page.toml include/exclude patterns into a relative-path map."""
    selected: dict[str, Path] = {}
    source_root = page.source.resolve()

    for pattern in page.include:
        matches = list(page.source.glob(pattern))
        if not matches:
            raise BuildError(
                f"{page.manifest_path}: include pattern matched nothing: {pattern!r}"
            )

        for match in matches:
            if match.is_dir():
                candidates = (path for path in match.rglob("*") if path.is_file())
            elif match.is_file():
                candidates = (match,)
            else:
                continue

            for path in candidates:
                relative = path.relative_to(page.source)
                relative_posix = relative.as_posix()
                if _is_excluded(relative_posix, page.exclude):
                    continue

                if path.is_symlink():
                    resolved = path.resolve()
                    try:
                        resolved.relative_to(source_root)
                    except ValueError as exc:
                        raise BuildError(
                            f"{page.manifest_path}: symlink escapes the page: {relative_posix}"
                        ) from exc

                selected[relative_posix] = path

    if page.entry not in selected:
        raise BuildError(
            f"{page.manifest_path}: entry {page.entry!r} is missing or excluded"
        )

    return selected


def _load_page_hook(page: Page) -> ModuleType | None:
    hook_path = page.source / PAGE_HOOK_NAME
    if not hook_path.is_file():
        return None

    module_name = f"_ellia_page_{page.slug}_{abs(hash(hook_path))}"
    spec = importlib.util.spec_from_file_location(module_name, hook_path)
    if spec is None or spec.loader is None:
        raise BuildError(f"{hook_path}: cannot load page build hook")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        sys.modules.pop(module_name, None)
        raise BuildError(f"{hook_path}: import failed: {exc}") from exc
    return module


def _run_hook(
    page: Page,
    hook: ModuleType | None,
    name: str,
    context: BuildContext,
) -> None:
    if hook is None:
        return
    function = getattr(hook, name, None)
    if function is None:
        return
    if not callable(function):
        raise BuildError(f"{page.source / PAGE_HOOK_NAME}: {name} is not callable")

    try:
        function(context)
    except BuildError:
        raise
    except Exception as exc:
        raise BuildError(
            f"{page.source / PAGE_HOOK_NAME}: {name} failed: {exc}"
        ) from exc


def _remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def _replace_with_stage(stage: Path, target: Path) -> None:
    """Replace target with stage, keeping the old directory until success."""
    old = target.with_name(f".{target.name}.old")
    _remove_path(old)
    moved_old = False

    if target.exists() or target.is_symlink():
        target.rename(old)
        moved_old = True

    try:
        stage.rename(target)
    except Exception:
        if moved_old and old.exists() and not target.exists():
            old.rename(target)
        raise

    _remove_path(old)


def _copy_files(files: dict[str, Path], stage: Path) -> None:
    for relative in sorted(files):
        destination = stage / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(files[relative], destination)


def _format_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if value < 1024 or unit == "GiB":
            if unit == "B":
                return f"{int(value)} B"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


def _tree_size(root: Path) -> tuple[int, int]:
    total = 0
    count = 0
    if not root.exists():
        return count, total
    for path in root.rglob("*"):
        if path.is_file():
            count += 1
            total += path.stat().st_size
    return count, total


def build_page(
    page: Page,
    out_root: Path,
    *,
    strict: bool,
    verbose: bool,
) -> tuple[int, int]:
    print(f"[page] {page.slug} — {page.title}")
    started = time.perf_counter()
    target = out_root / page.slug
    stage = out_root / f".{page.slug}.tmp"
    _remove_path(stage)
    stage.mkdir(parents=True)

    context = BuildContext(
        page=page,
        stage=stage,
        out_root=out_root,
        strict=strict,
        verbose=verbose,
    )
    hook: ModuleType | None = None

    try:
        hook = _load_page_hook(page)
        _run_hook(page, hook, "prebuild", context)

        files = _collect_files(page)
        source_size = sum(path.stat().st_size for path in files.values())
        context.log(f"copying {len(files)} files ({_format_size(source_size)})")
        _copy_files(files, stage)

        _run_hook(page, hook, "postbuild", context)

        if strict and context.warnings:
            raise BuildError(
                f"{page.slug}: {len(context.warnings)} warning(s) treated as errors by --strict"
            )

        _replace_with_stage(stage, target)
        count, size = _tree_size(target)
        elapsed = time.perf_counter() - started
        print(
            f"  [ok] {count} files, {_format_size(size)} "
            f"-> {target} ({elapsed:.2f}s)"
        )
        return count, size
    finally:
        if stage.exists() or stage.is_symlink():
            _remove_path(stage)


def _resolve_out_root(value: str, pages: list[Page]) -> Path:
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    out_root = candidate.resolve()

    if out_root == ROOT or out_root in ROOT.parents:
        raise BuildError(f"refusing to use the project root as output: {out_root}")

    reserved = [
        ROOT / ".git",
        ROOT / ".venv",
        ROOT / ".dsh",
        ROOT / ".opencode",
        ROOT / ".ref",
        ROOT / "openspec",
    ]
    for path in reserved:
        if out_root == path or path in out_root.parents:
            raise BuildError(f"refusing to write build output into {path.name}/")

    for page in pages:
        source = page.source.resolve()
        if out_root == source or source in out_root.parents:
            raise BuildError(
                f"refusing to write build output inside page source: {source}"
            )

    if out_root.exists() and not out_root.is_dir():
        raise BuildError(f"output path exists and is not a directory: {out_root}")

    return out_root


def _select_pages(pages: list[Page], requested: list[str], all_pages: bool) -> list[Page]:
    if all_pages and requested:
        raise BuildError("--all cannot be combined with explicit page names")

    if not requested:
        return pages

    by_slug = {page.slug: page for page in pages}
    selected: list[Page] = []
    seen: set[str] = set()
    unknown: list[str] = []

    for name in requested:
        slug = name.strip().rstrip("/\\")
        if not slug:
            continue
        page = by_slug.get(slug)
        if page is None:
            unknown.append(slug)
            continue
        if page.slug not in seen:
            selected.append(page)
            seen.add(page.slug)

    if unknown:
        available = ", ".join(sorted(by_slug)) or "(none)"
        raise BuildError(f"unknown page(s): {', '.join(unknown)}; available: {available}")
    if not selected:
        raise BuildError("no page selected")
    return selected


def _print_pages(pages: list[Page], out_root: Path) -> None:
    print(f"project: {ROOT}")
    print(f"output:  {out_root}")
    print(f"pages:   {len(pages)}")
    for page in pages:
        print(
            f"  {page.slug:<16} entry={page.entry:<16} "
            f"include={len(page.include)} exclude={len(page.exclude)}"
        )


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build static ellia-pages pages into dist/",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Page layout:\n"
            "  <page>/page.toml   required manifest\n"
            "  <page>/build.py    optional prebuild/postbuild hooks\n"
            "  <page>/.gitignore  page-local ignores\n"
        ),
    )
    parser.add_argument("pages", nargs="*", metavar="PAGE", help="page directory name")
    parser.add_argument(
        "--all",
        action="store_true",
        help="build every discovered page (default when PAGE is omitted)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="list discovered pages and exit",
    )
    parser.add_argument(
        "--out",
        default=DEFAULT_OUT,
        metavar="DIR",
        help=f"output directory (default: {DEFAULT_OUT}/)",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="remove the output directory before building",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="treat page build warnings as errors",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="show per-page detail",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)

    try:
        pages = discover_pages(ROOT)
        if not pages:
            raise BuildError(
                f"no pages found; add <page>/{MANIFEST_NAME} under {ROOT}"
            )

        out_root = _resolve_out_root(args.out, pages)

        if args.list:
            _print_pages(pages, out_root)
            return 0

        selected = _select_pages(pages, args.pages, args.all)
        if args.clean and out_root.exists():
            print(f"[clean] {out_root}")
            _remove_path(out_root)
        out_root.mkdir(parents=True, exist_ok=True)

        started = time.perf_counter()
        total_files = 0
        total_bytes = 0
        for page in selected:
            count, size = build_page(
                page,
                out_root,
                strict=args.strict,
                verbose=args.verbose,
            )
            total_files += count
            total_bytes += size

        elapsed = time.perf_counter() - started
        print(
            f"[done] {len(selected)} page(s), {total_files} files, "
            f"{_format_size(total_bytes)} -> {out_root} ({elapsed:.2f}s)"
        )
        return 0
    except BuildError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("[error] interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
