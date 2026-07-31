"""
Core file organization engine for File Auto-Organizer.

Handles category matching, collision resolution (numeric/timestamp),
safe path generation, dry-run mode, and atomic file movement.
"""

from __future__ import annotations

import datetime
import logging
import os
import shutil
from pathlib import Path
from typing import NamedTuple, Sequence

from file_organizer.config import AppConfig, CategoryConfig, resolve_path
from file_organizer.logger import get_logger

logger = get_logger()


class FileMoveResult(NamedTuple):
    """Result of an organize operation on a single file."""
    source: Path
    destination: Path | None
    category: str | None
    moved: bool
    collision_resolved: bool
    error: str | None = None


def extract_extension(path: Path, compound_extensions: tuple[str, ...] = ()) -> tuple[str, str]:
    """
    Extract the base name and extension from a path, properly handling
    compound extensions like .tar.gz, .tar.bz2, etc.

    Args:
        path: Path object to examine.
        compound_extensions: Tuple of recognized compound extensions (e.g. ('.tar.gz', ...))
            sorted by length descending.

    Returns:
        tuple of (stem_name, extension) where extension includes leading dot and is lowercase.
        Example: ("archive", ".tar.gz") or ("document", ".pdf")
    """
    filename = path.name
    lower_name = filename.lower()

    # Check compound extensions first (greedy match)
    for comp in compound_extensions:
        if lower_name.endswith(comp):
            stem = filename[:-len(comp)]
            return stem, comp

    # Standard suffix fallback
    suffix = path.suffix.lower()
    if suffix:
        stem = filename[:-len(suffix)]
        return stem, suffix

    return filename, ""


def get_category_for_file(file_path: Path, config: AppConfig) -> CategoryConfig | None:
    """
    Determine the category for a given file based on its extension.

    Args:
        file_path: Path to the file.
        config: Loaded application configuration.

    Returns:
        CategoryConfig if matched, or None if no category matches.
    """
    _, ext = extract_extension(file_path, config.compound_extensions)
    if not ext:
        return None

    return config.extension_map.get(ext)


def find_enclosing_watch_directory(file_path: Path, config: AppConfig) -> Path:
    """
    Find which configured watch directory contains the given file.
    Returns the closest ancestor watch directory, or falls back to config.watch_directory.
    """
    try:
        resolved_file = file_path.resolve()
        matches: list[Path] = []
        for wd in config.watch_directories:
            try:
                resolved_wd = wd.resolve()
                if resolved_file == resolved_wd or resolved_wd in resolved_file.parents:
                    matches.append(resolved_wd)
            except OSError:
                continue
        if matches:
            # If multiple (e.g. nested watch dirs), pick the deepest/most specific
            matches.sort(key=lambda p: len(p.parts), reverse=True)
            return matches[0]
    except OSError:
        pass
    return config.watch_directory


def get_destination_for_file(
    source_path: Path,
    category_cfg: CategoryConfig | None,
    config: AppConfig,
) -> tuple[str | None, Path | None]:
    """
    Determine the category name and destination directory for a source file.
    Relative category folders are anchored to the file's enclosing watch directory.
    """
    base_watch_dir = find_enclosing_watch_directory(source_path, config)

    if category_cfg is not None:
        category_name = category_cfg.name
        if category_cfg.is_custom_absolute:
            dest_dir = category_cfg.folder
        else:
            dest_dir = resolve_path(category_cfg.raw_folder, base_dir=base_watch_dir)
        return category_name, dest_dir
    elif config.unmatched_category:
        category_name = config.unmatched_category
        raw_unmatched = config.unmatched_category
        is_abs = Path(os.path.expanduser(raw_unmatched)).is_absolute()
        if is_abs:
            dest_dir = resolve_path(raw_unmatched)
        else:
            dest_dir = resolve_path(raw_unmatched, base_dir=base_watch_dir)
        return category_name, dest_dir

    return None, None


def is_inside_destination(path: Path, config: AppConfig) -> bool:
    """
    Check if a given path is already located inside any configured category folder
    across all monitored directories. Prevents cyclic moving of already organized files.
    """
    try:
        resolved_path = path.resolve()
        for cat in config.categories.values():
            if cat.is_custom_absolute:
                cat_dir = cat.folder.resolve()
                if resolved_path == cat_dir or cat_dir in resolved_path.parents:
                    return True
            else:
                for wd in config.watch_directories:
                    cat_dir = (wd / cat.raw_folder).resolve()
                    if resolved_path == cat_dir or cat_dir in resolved_path.parents:
                        return True

        if config.unmatched_category:
            raw_unmatched = config.unmatched_category
            if Path(os.path.expanduser(raw_unmatched)).is_absolute():
                unmatched_dir = resolve_path(raw_unmatched)
                if resolved_path == unmatched_dir or unmatched_dir in resolved_path.parents:
                    return True
            else:
                for wd in config.watch_directories:
                    unmatched_dir = (wd / raw_unmatched).resolve()
                    if resolved_path == unmatched_dir or unmatched_dir in resolved_path.parents:
                        return True
    except OSError:
        pass
    return False


def resolve_collision(
    dest_path: Path,
    strategy: str = "numeric",
    compound_extensions: tuple[str, ...] = ()
) -> Path | None:
    """
    Resolve destination file name collision if dest_path already exists.

    Args:
        dest_path: Intended destination file path.
        strategy: 'numeric', 'timestamp', or 'skip'.
        compound_extensions: Recognized compound extensions for correct stem splitting.

    Returns:
        Resolved non-colliding Path, or None if strategy is 'skip'.
    """
    if not dest_path.exists():
        return dest_path

    if strategy == "skip":
        return None

    stem, ext = extract_extension(dest_path, compound_extensions)
    parent_dir = dest_path.parent

    if strategy == "numeric":
        counter = 1
        while True:
            candidate = parent_dir / f"{stem} ({counter}){ext}"
            if not candidate.exists():
                return candidate
            counter += 1

    if strategy == "timestamp":
        now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        candidate = parent_dir / f"{stem}_{now_str}{ext}"
        if not candidate.exists():
            return candidate
        # In case rapid moves happen in the same second
        counter = 1
        while True:
            candidate = parent_dir / f"{stem}_{now_str}_{counter}{ext}"
            if not candidate.exists():
                return candidate
            counter += 1

    # Fallback to numeric
    counter = 1
    while True:
        candidate = parent_dir / f"{stem} ({counter}){ext}"
        if not candidate.exists():
            return candidate
        counter += 1


def organize_file(
    source_path: Path,
    config: AppConfig,
    dry_run: bool = False,
) -> FileMoveResult:
    """
    Organize a single file according to configuration rules.

    Args:
        source_path: Path to the source file to organize.
        config: Application configuration.
        dry_run: If True, do not modify the filesystem; only simulate and log.

    Returns:
        FileMoveResult describing the outcome.
    """
    try:
        resolved_source = source_path.resolve()
    except OSError as e:
        logger.error(f"Cannot resolve path '{source_path}': {e}")
        return FileMoveResult(source_path, None, None, False, False, str(e))

    # 1. Existence and type verification
    if not resolved_source.is_file():
        return FileMoveResult(source_path, None, None, False, False, "Not a regular file")

    # 2. Hidden file check
    if config.ignore_hidden and source_path.name.startswith("."):
        logger.debug(f"Ignoring hidden file: {source_path.name}")
        return FileMoveResult(source_path, None, None, False, False, "Hidden file ignored")

    # 3. Check if file is already inside any destination folder
    if is_inside_destination(resolved_source, config):
        logger.debug(f"File is already inside a destination folder: {source_path.name}")
        return FileMoveResult(source_path, None, None, False, False, "Already inside destination")

    # 4. Determine target category and folder
    category_cfg = get_category_for_file(source_path, config)
    category_name, dest_dir = get_destination_for_file(source_path, category_cfg, config)
    if dest_dir is None:
        logger.debug(f"No category matched and unmatched action is 'leave': {source_path.name}")
        return FileMoveResult(source_path, None, None, False, False, "No category matched (left in place)")

    # 5. Destination path computation
    target_dest = dest_dir / source_path.name
    collision_resolved = False

    # Check for collision
    final_dest = resolve_collision(
        dest_path=target_dest,
        strategy=config.conflict_resolution,
        compound_extensions=config.compound_extensions,
    )

    if final_dest is None:
        logger.warning(f"File '{source_path.name}' already exists in '{dest_dir}'. Skipped (strategy='skip').")
        return FileMoveResult(source_path, target_dest, category_name, False, False, "Skipped due to collision")

    if final_dest != target_dest:
        collision_resolved = True

    # 6. Execute move (or simulate in dry-run)
    if dry_run:
        prefix = "[DRY-RUN] "
        if not dest_dir.exists():
            logger.info(f"{prefix}Would create folder: {dest_dir}")
        if collision_resolved:
            logger.info(f"{prefix}Would resolve collision: {target_dest.name} -> {final_dest.name}")
        logger.info(f"{prefix}Would move: {source_path} -> {final_dest}")
        return FileMoveResult(source_path, final_dest, category_name, True, collision_resolved)

    try:
        # Create destination directory if needed
        if not dest_dir.exists():
            dest_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created folder: {dest_dir}")

        # Atomic move or cross-device copy+remove handled by shutil.move
        shutil.move(str(resolved_source), str(final_dest))

        if collision_resolved:
            logger.info(
                f"Moved (Collision resolved): '{source_path.name}' -> '{dest_dir.name}/{final_dest.name}'"
            )
        else:
            logger.info(f"Moved: '{source_path.name}' -> '{dest_dir.name}/{final_dest.name}'")

        return FileMoveResult(source_path, final_dest, category_name, True, collision_resolved)

    except PermissionError as e:
        msg = f"Permission denied moving '{source_path}': {e}"
        logger.error(msg)
        return FileMoveResult(source_path, final_dest, category_name, False, collision_resolved, msg)
    except OSError as e:
        msg = f"OS error moving '{source_path}' to '{final_dest}': {e}"
        logger.error(msg)
        return FileMoveResult(source_path, final_dest, category_name, False, collision_resolved, msg)


def organize_directory(
    watch_dir: Path,
    config: AppConfig,
    dry_run: bool = False,
) -> tuple[int, int]:
    """
    Scan and organize all eligible files in the target directory.

    Args:
        watch_dir: Directory containing files to organize.
        config: Application configuration.
        dry_run: If True, simulate actions without modifying filesystem.

    Returns:
        tuple of (moved_count, skipped_or_failed_count).
    """
    if not watch_dir.exists():
        logger.error(f"Target directory does not exist: {watch_dir}")
        return 0, 0

    logger.info(f"Scanning directory for files to organize: {watch_dir} (dry_run={dry_run})")
    moved_count = 0
    skipped_count = 0

    try:
        entries = sorted(watch_dir.iterdir(), key=lambda p: p.name.lower())
    except OSError as e:
        logger.error(f"Failed to list directory '{watch_dir}': {e}")
        return 0, 0

    for entry in entries:
        if not entry.is_file():
            continue

        result = organize_file(entry, config, dry_run=dry_run)
        if result.moved:
            moved_count += 1
        else:
            skipped_count += 1

    mode_str = " (DRY RUN)" if dry_run else ""
    logger.info(
        f"Scan complete{mode_str}: {moved_count} file(s) organized, {skipped_count} skipped/unaltered."
    )
    return moved_count, skipped_count


def organize_directories(
    watch_dirs: Sequence[Path],
    config: AppConfig,
    dry_run: bool = False,
) -> tuple[int, int]:
    """
    Scan and organize all eligible files across multiple target directories.

    Args:
        watch_dirs: Sequence of directories containing files to organize.
        config: Application configuration.
        dry_run: If True, simulate actions without modifying filesystem.

    Returns:
        tuple of (total_moved_count, total_skipped_count).
    """
    total_moved = 0
    total_skipped = 0
    for directory in watch_dirs:
        moved, skipped = organize_directory(
            watch_dir=directory,
            config=config,
            dry_run=dry_run,
        )
        total_moved += moved
        total_skipped += skipped
    return total_moved, total_skipped
