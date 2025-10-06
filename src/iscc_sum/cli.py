# Command-line interface for iscc-sum tool

from __future__ import annotations

import sys
from contextlib import contextmanager
from importlib.metadata import PackageNotFoundError, version
from typing import IO, Any, Iterator

import click

# Constants
IO_READ_SIZE = 2097152  # 2MB chunk size

# Exit codes
EXIT_SUCCESS = 0
EXIT_VERIFICATION_FAILURE = 1
EXIT_ERROR = 2


def _normalize_path_display(path):
    # type: (str) -> str
    """Normalize file path for display by converting backslashes to forward slashes.

    This ensures consistent output across platforms, particularly on Windows.

    Args:
        path: The file path to normalize

    Returns:
        Normalized path with forward slashes
    """
    if path == "-":  # stdin
        return path
    return path.replace("\\", "/")


def get_version():
    # type: () -> str
    """Get the version of iscc-sum package."""
    try:
        return version("iscc-sum")
    except PackageNotFoundError:
        return "0.1.0-alpha.1"  # Fallback version


@contextmanager
def output_file_context(output_path):
    # type: (str | None) -> Iterator[IO[Any] | None]
    """Context manager to open output file or return None for stdout.

    Args:
        output_path: Path to output file, or None for stdout

    Yields:
        File handle or None

    Raises:
        IOError: If file cannot be opened for writing
    """
    if output_path is None:
        # Use stdout - yield None to signal stdout usage
        yield None
    else:
        # Open file with UTF-8 encoding and LF line endings
        try:
            with open(output_path, "w", encoding="utf-8", newline="\n") as f:
                yield f
        except IOError as e:
            click.echo(f"iscc-sum: {output_path}: {e}", err=True)
            sys.exit(EXIT_ERROR)


@click.command(
    context_settings={"help_option_names": ["-h", "--help"]},
    epilog="Exit status: 0 if OK, 1 if checksum verification fails, 2 if trouble.",
)
@click.version_option(version=get_version(), prog_name="iscc-sum")
@click.option(
    "-c",
    "--check",
    is_flag=True,
    help="Read checksums from FILEs and verify them",
)
@click.option(
    "--tag",
    is_flag=True,
    help="Create a BSD-style checksum output",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    help="Write checksums to FILE instead of stdout (ensures UTF-8, LF encoding)",
)
@click.option(
    "-z",
    "--zero",
    is_flag=True,
    help="End each output line with NUL, not newline",
)
@click.option(
    "-q",
    "--quiet",
    is_flag=True,
    help="Don't print OK for successfully verified files",
)
@click.option(
    "--status",
    is_flag=True,
    help="Don't output anything, status code shows success",
)
@click.option(
    "-w",
    "--warn",
    is_flag=True,
    help="Warn about improperly formatted checksum lines",
)
@click.option(
    "--strict",
    is_flag=True,
    help="Exit non-zero for improperly formatted checksum lines",
)
@click.option(
    "--narrow",
    is_flag=True,
    help="Generate narrow format (2×64-bit ISO 24138:2024 conformant) (default: 2×128-bit extended format)",
)
@click.option(
    "--units",
    is_flag=True,
    help="Include individual Data-Code and Instance-Code units in output (verification mode: ignored)",
)
@click.option(
    "--similar",
    is_flag=True,
    help="Group files by similarity based on Data-Code hamming distance",
)
@click.option(
    "--threshold",
    type=click.IntRange(min=0),
    default=12,
    show_default=True,
    help="Maximum hamming distance for similarity matching",
)
@click.option(
    "-t",
    "--tree",
    is_flag=True,
    help="Process directory as a single unit with combined checksum",
)
@click.option(
    "--walk",
    is_flag=True,
    help="List files in processing order (same as --tree but without checksum computation)",
)
@click.argument("files", nargs=-1, type=click.Path())
def cli(
    check,
    tag,
    output,
    zero,
    quiet,
    status,
    warn,
    strict,
    narrow,
    units,
    similar,
    threshold,
    tree,
    walk,
    files,
):
    # type: (bool, bool, str | None, bool, bool, bool, bool, bool, bool, bool, bool, int, bool, bool, tuple) -> None
    """Compute ISCC (International Standard Content Code) checksums for files.

    Each checksum consists of a 2-byte self-describing header followed by a
    composite of Data-Code and Instance-Code (BLAKE3) components. All files
    are processed as binary data.

    Unlike traditional checksum tools that only verify exact matches, iscc-sum
    enables similarity detection between files through the Data-Code component.
    Files with similar content will have similar Data-Codes, allowing similarity
    matching based on hamming distance.

    \b
    Examples:
      # Generate checksums
      iscc-sum document.pdf
      iscc-sum *.txt

      # Verify checksums
      iscc-sum -c checksums.txt

      # Find similar files
      iscc-sum --similar *.jpg
    """
    # Validate conflicting options
    if output and check:
        click.echo("iscc-sum: -o/--output cannot be used with -c/--check", err=True)
        sys.exit(EXIT_ERROR)

    if similar and check:
        click.echo("iscc-sum: --similar cannot be used with -c/--check", err=True)
        sys.exit(EXIT_ERROR)

    if tree and check:
        click.echo("iscc-sum: --tree cannot be used with -c/--check", err=True)
        sys.exit(EXIT_ERROR)

    if tree and similar:
        click.echo("iscc-sum: --tree cannot be used with --similar", err=True)
        sys.exit(EXIT_ERROR)

    if walk and check:
        click.echo("iscc-sum: --walk cannot be used with -c/--check", err=True)
        sys.exit(EXIT_ERROR)

    if walk and similar:
        click.echo("iscc-sum: --walk cannot be used with --similar", err=True)
        sys.exit(EXIT_ERROR)

    if walk and tree:
        click.echo("iscc-sum: --walk cannot be used with --tree", err=True)
        sys.exit(EXIT_ERROR)

    if similar and len(files) < 2:
        click.echo("iscc-sum: --similar requires at least 2 files to compare", err=True)
        sys.exit(EXIT_ERROR)

    if tree and len(files) != 1:
        click.echo("iscc-sum: --tree requires exactly one directory argument", err=True)
        sys.exit(EXIT_ERROR)

    if walk and len(files) != 1:
        click.echo("iscc-sum: --walk requires exactly one directory argument", err=True)
        sys.exit(EXIT_ERROR)

    if tree or walk:
        # Validate that the argument is a directory
        from pathlib import Path

        if not Path(files[0]).is_dir():
            mode_name = "--tree" if tree else "--walk"
            click.echo(f"iscc-sum: {mode_name} requires a directory, not a file: '{files[0]}'", err=True)
            sys.exit(EXIT_ERROR)

    try:
        if check:
            # Verification mode (no output file needed)
            _handle_verification(files, quiet, status, warn, strict)
        else:
            # Generation modes - use output file context
            with output_file_context(output) as output_file:
                if similar:
                    # Similarity matching mode
                    _handle_similarity(files, threshold, narrow, tag, zero, output_file)
                elif tree:
                    # Tree mode - process directory as single unit
                    _handle_tree_mode(files[0], narrow, units, tag, zero, output_file)
                elif walk:
                    # Walk mode - list files in processing order
                    _handle_tree_mode(files[0], narrow, units, tag, zero, output_file, list_only=True)
                else:
                    # Normal checksum generation mode
                    _handle_checksum_generation(files, narrow, units, tag, zero, output_file)
    except Exception as e:
        click.echo(f"iscc-sum: {e}", err=True)
        sys.exit(EXIT_ERROR)

    sys.exit(EXIT_SUCCESS)


def _expand_paths(paths):
    # type: (tuple) -> Iterator[str]
    """Expand file and directory paths to individual file paths.

    For file paths, yield as-is. For directory paths, use treewalk_iscc
    to get all files in deterministic order.

    Args:
        paths: Tuple of file/directory paths

    Yields:
        Individual file paths
    """
    from pathlib import Path

    from iscc_sum.treewalk import treewalk_iscc

    for path in paths:
        path_obj = Path(path)

        # Check if path exists
        if not path_obj.exists():
            raise IOError(f"No such file or directory: '{path}'")

        if path_obj.is_file():
            # Yield file path as-is, preserving original format
            yield path
        elif path_obj.is_dir():
            # Get the absolute path of the directory for comparison
            dir_absolute = path_obj.resolve()

            # Use treewalk_iscc for deterministic directory traversal
            for file_path in treewalk_iscc(path_obj):
                # Make path relative to the original directory
                relative_path = file_path.relative_to(dir_absolute)
                # Create output path with forward slashes for consistency
                # Join original path with relative path using forward slashes
                output_path = path + "/" + relative_path.as_posix()
                yield output_path
        else:
            # Not a regular file or directory (e.g., device, pipe)
            raise IOError(f"Not a regular file or directory: '{path}'")


def _handle_tree_mode(directory, narrow, units, tag, zero, output_file=None, list_only=False):
    # type: (str, bool, bool, bool, bool, IO[Any] | None, bool) -> None
    """Handle tree mode - process directory as single unit or list files."""
    from pathlib import Path

    from iscc_sum import IsccSumProcessor
    from iscc_sum.treewalk import treewalk_iscc

    try:
        # Create a single processor for the entire directory (unless list_only)
        if not list_only:
            processor = IsccSumProcessor()

        # Process all files in the directory in deterministic order
        file_count = 0
        dir_path = Path(directory).resolve()

        for file_path in treewalk_iscc(Path(directory)):
            file_count += 1

            if list_only:
                # Just output the file path relative to the directory
                relative_path = file_path.relative_to(dir_path)
                display_path = _normalize_path_display(str(relative_path))

                terminator = "\0" if zero else "\n"
                click.echo(display_path, nl=False, file=output_file)
                click.echo(terminator, nl=False, file=output_file)
            else:
                # Process file for checksum computation
                try:
                    with open(file_path, "rb") as f:
                        while True:
                            chunk = f.read(IO_READ_SIZE)
                            if not chunk:
                                break
                            processor.update(chunk)
                except IOError as e:
                    # Report but continue processing other files
                    click.echo(f"iscc-sum: {file_path}: {e}", err=True)
                    continue

        if file_count == 0:
            click.echo(f"iscc-sum: {directory}: no files found", err=True)
            sys.exit(EXIT_ERROR)

        # Only compute and output checksum if not in list_only mode
        if not list_only:
            # Get result
            result = processor.result(wide=not narrow, add_units=units)

            # Format output with trailing slash to indicate tree mode
            terminator = "\0" if zero else "\n"
            display_name = _normalize_path_display(directory.rstrip("/") + "/")

            if tag:
                # BSD-style output
                output = "ISCC-SUM ({}) = {}".format(display_name, result.iscc)
            else:
                # Default output format
                output = "{} *{}".format(result.iscc, display_name)

            click.echo(output, nl=False, file=output_file)
            click.echo(terminator, nl=False, file=output_file)

            # Display units if requested
            if units and result.units:
                for unit in result.units:
                    unit_output = "  {}".format(unit)
                    click.echo(unit_output, nl=False, file=output_file)
                    click.echo(terminator, nl=False, file=output_file)

    except Exception as e:
        error_msg = "iscc-sum: {}: unexpected error: {}".format(directory, str(e))
        click.echo(error_msg, err=True)
        sys.exit(EXIT_ERROR)


def _handle_checksum_generation(files, narrow, units, tag, zero, output_file=None):
    # type: (tuple, bool, bool, bool, bool, IO[Any] | None) -> None
    """Handle normal checksum generation mode."""
    import os

    from iscc_sum import IsccSumProcessor

    if not files:
        # Read from stdin
        files = ("-",)

    # Handle stdin separately as it's not a path
    if files == ("-",):
        file_paths = ["-"]
    else:
        # Expand directories to files
        file_paths = list(_expand_paths(files))

    for filepath in file_paths:
        try:
            processor = IsccSumProcessor()

            # Handle stdin
            if filepath == "-":
                # Use binary buffer for stdin
                stdin = sys.stdin.buffer

                while True:
                    chunk = stdin.read(IO_READ_SIZE)
                    if not chunk:
                        break
                    processor.update(chunk)

                display_name = "-"
            else:
                # Handle regular file
                with open(filepath, "rb") as f:
                    while True:
                        chunk = f.read(IO_READ_SIZE)
                        if not chunk:
                            break
                        processor.update(chunk)

                display_name = _normalize_path_display(filepath)

            # Get result
            result = processor.result(wide=not narrow, add_units=units)

            # Format output
            terminator = "\0" if zero else "\n"

            if tag:
                # BSD-style output
                output = "ISCC-SUM ({}) = {}".format(display_name, result.iscc)
            else:
                # Default output format
                output = "{} *{}".format(result.iscc, display_name)

            click.echo(output, nl=False, file=output_file)
            click.echo(terminator, nl=False, file=output_file)

            # Display units if requested
            if units and result.units:
                for unit in result.units:
                    unit_output = "  {}".format(unit)
                    click.echo(unit_output, nl=False, file=output_file)
                    click.echo(terminator, nl=False, file=output_file)

        except IOError as e:
            error_msg = "iscc-sum: {}: {}".format(filepath, str(e))
            click.echo(error_msg, err=True)
            sys.exit(EXIT_ERROR)
        except Exception as e:
            error_msg = "iscc-sum: {}: unexpected error: {}".format(filepath, str(e))
            click.echo(error_msg, err=True)
            sys.exit(EXIT_ERROR)


def _parse_checksum_line(line):
    # type: (str) -> tuple | None
    """Parse a checksum line in either default or BSD format.

    Returns (iscc_code, filename, is_tree_mode) tuple or None if invalid format.
    The is_tree_mode flag indicates if the filename ends with a slash (tree mode).
    """
    import re

    # BSD format: ISCC-SUM (filename) = ISCC:xxx
    bsd_match = re.match(r"^ISCC-SUM \((.+)\) = (ISCC:[A-Z0-9]+)$", line)
    if bsd_match:
        filename = bsd_match.group(1)
        iscc_code = bsd_match.group(2)
        is_tree_mode = filename.endswith("/")
        return iscc_code, filename, is_tree_mode

    # Default format: ISCC:xxx *filename
    default_match = re.match(r"^(ISCC:[A-Z0-9]+) \*(.+)$", line)
    if default_match:
        iscc_code = default_match.group(1)
        filename = default_match.group(2)
        is_tree_mode = filename.endswith("/")
        return iscc_code, filename, is_tree_mode

    return None


def _handle_verification(files, quiet, status, warn, strict):
    # type: (tuple, bool, bool, bool, bool) -> None
    """Handle checksum verification mode."""
    import os

    from iscc_sum import IsccSumProcessor

    if not files:
        click.echo("iscc-sum: no checksum file specified", err=True)
        sys.exit(EXIT_ERROR)

    total_files = 0
    failed_files = 0
    missing_files = 0
    format_errors = 0

    for checksum_file in files:
        try:
            with open(checksum_file, "r", encoding="utf-8") as f:
                line_number = 0
                for line in f:
                    line_number += 1
                    line = line.rstrip("\n\r")

                    # Strip BOM if present (can occur on first line)
                    if line_number == 1 and line.startswith("\ufeff"):
                        line = line[1:]

                    if not line:
                        continue

                    # Parse the checksum line
                    parsed = _parse_checksum_line(line)
                    if parsed is None:
                        format_errors += 1
                        if warn:
                            click.echo(
                                f"iscc-sum: {checksum_file}: {line_number}: "
                                f"improperly formatted ISCC checksum line",
                                err=True,
                            )
                        if strict:
                            sys.exit(EXIT_ERROR)
                        continue

                    expected_iscc, filename, is_tree_mode = parsed
                    total_files += 1

                    # For tree mode, remove the trailing slash to get the directory path
                    if is_tree_mode:
                        directory = filename.rstrip("/")

                        # Check if directory exists
                        if not os.path.exists(directory):
                            missing_files += 1
                            if not status:
                                click.echo(f"iscc-sum: {directory}: No such file or directory")
                            failed_files += 1
                            continue

                        if not os.path.isdir(directory):
                            failed_files += 1
                            if not status:
                                click.echo(f"iscc-sum: {directory}: Not a directory")
                            continue

                        # Calculate tree checksum
                        try:
                            from iscc_sum.treewalk import treewalk_iscc

                            processor = IsccSumProcessor()

                            # Process all files in the directory in order
                            for file_path in treewalk_iscc(directory):
                                try:
                                    with open(file_path, "rb") as tree_file:
                                        while True:
                                            chunk = tree_file.read(IO_READ_SIZE)
                                            if not chunk:
                                                break
                                            processor.update(chunk)
                                except IOError:
                                    # Skip files we can't read (matches tree mode generation behavior)
                                    continue

                            # Determine if expected is narrow or wide format
                            is_narrow = len(expected_iscc) < 35
                            result = processor.result(wide=not is_narrow, add_units=False)
                            actual_iscc = result.iscc

                            # Compare checksums
                            if actual_iscc == expected_iscc:
                                if not quiet and not status:
                                    click.echo(f"{filename}: OK")
                            else:
                                failed_files += 1
                                if not status:
                                    click.echo(f"{filename}: FAILED")

                        except Exception as e:
                            failed_files += 1
                            if not status:
                                click.echo(f"iscc-sum: {directory}: {e}")
                    else:
                        # Regular file verification
                        # Check if file exists
                        if not os.path.exists(filename):
                            missing_files += 1
                            if not status:
                                click.echo(f"iscc-sum: {filename}: No such file or directory")
                            failed_files += 1
                            continue

                        # Calculate actual checksum
                        try:
                            processor = IsccSumProcessor()
                            with open(filename, "rb") as target_file:
                                while True:
                                    chunk = target_file.read(IO_READ_SIZE)
                                    if not chunk:
                                        break
                                    processor.update(chunk)

                            # Determine if expected is narrow or wide format
                            is_narrow = len(expected_iscc) < 35
                            result = processor.result(wide=not is_narrow, add_units=False)
                            actual_iscc = result.iscc

                            # Compare checksums
                            if actual_iscc == expected_iscc:
                                if not quiet and not status:
                                    click.echo(f"{filename}: OK")
                            else:
                                failed_files += 1
                                if not status:
                                    click.echo(f"{filename}: FAILED")

                        except IOError as e:
                            failed_files += 1
                            if not status:
                                click.echo(f"iscc-sum: {filename}: {e}")

        except IOError as e:
            click.echo(f"iscc-sum: {checksum_file}: {e}", err=True)
            sys.exit(EXIT_ERROR)

    # Display summary if there were any issues
    if not status and (failed_files > 0 or format_errors > 0):
        if format_errors > 0:
            click.echo(f"iscc-sum: WARNING: {format_errors} line(s) improperly formatted", err=True)
        if failed_files > 0:
            click.echo(f"iscc-sum: WARNING: {failed_files} computed checksum(s) did NOT match", err=True)

    # Exit with appropriate code
    if failed_files > 0:
        sys.exit(EXIT_VERIFICATION_FAILURE)


def _extract_data_code_bits(iscc_string, narrow):
    # type: (str, bool) -> bytes
    """Extract Data-Code bits from an ISCC string.

    Args:
        iscc_string: The ISCC string (e.g., "ISCC:KAD4...")
        narrow: Whether this is a narrow format ISCC

    Returns:
        The raw Data-Code bits as bytes
    """
    import base64

    # Remove ISCC: prefix and decode from base32
    iscc_clean = iscc_string.replace("ISCC:", "")

    # Pad to make length multiple of 8 for base32 decoding
    padding = (8 - len(iscc_clean) % 8) % 8
    iscc_padded = iscc_clean + "=" * padding

    # Decode from base32 (RFC4648)
    # ISCC codes should always decode properly with correct padding
    decoded = base64.b32decode(iscc_padded)

    # Skip the 2-byte header
    # Data-Code is the first component after header
    if narrow:
        # Narrow format: 64-bit Data-Code (8 bytes)
        return decoded[2:10]  # bytes 2-9
    else:
        # Extended format: 128-bit Data-Code (16 bytes)
        return decoded[2:18]  # bytes 2-17


def _hamming_distance(bits_a, bits_b):
    # type: (bytes, bytes) -> int
    """Calculate hamming distance between two byte sequences.

    Args:
        bits_a: First byte sequence
        bits_b: Second byte sequence

    Returns:
        Number of differing bits
    """
    if len(bits_a) != len(bits_b):
        raise ValueError("Byte sequences must have equal length")

    distance = 0
    for a, b in zip(bits_a, bits_b):
        # XOR the bytes and count the number of 1 bits
        xor_result = a ^ b
        # Count bits set to 1 (Brian Kernighan's algorithm)
        while xor_result:
            distance += 1
            xor_result &= xor_result - 1

    return distance


def _handle_similarity(files, threshold, narrow, tag, zero, output_file=None):
    # type: (tuple, int, bool, bool, bool, IO[Any] | None) -> None
    """Handle similarity matching mode."""
    from iscc_sum import IsccSumProcessor

    # Process all files and compute their ISCCs
    file_data = []  # List of (filepath, iscc, data_code_bits)

    # Expand directories to files
    file_paths = list(_expand_paths(files))

    for filepath in file_paths:
        try:
            # Process file to get ISCC
            processor = IsccSumProcessor()
            with open(filepath, "rb") as f:
                while True:
                    chunk = f.read(IO_READ_SIZE)
                    if not chunk:
                        break
                    processor.update(chunk)

            result = processor.result(wide=not narrow, add_units=False)

            # Extract Data-Code bits from ISCC for comparison
            data_code_bits = _extract_data_code_bits(result.iscc, narrow)
            file_data.append((filepath, result.iscc, data_code_bits))

        except IOError as e:
            click.echo(f"iscc-sum: {filepath}: {e}", err=True)
            sys.exit(EXIT_ERROR)

    # The CLI already validates that we have at least 2 files,
    # so we don't need to handle empty or single file cases

    # Find similar files for each reference file
    processed = set()  # Track which files have been output
    group_count = 0

    for i, (ref_path, ref_iscc, ref_bits) in enumerate(file_data):
        if ref_path in processed:
            continue

        # Find all files similar to this reference file
        similar_files = []

        for j, (comp_path, comp_iscc, comp_bits) in enumerate(file_data):
            if i == j:  # Skip self-comparison
                continue

            # Calculate hamming distance
            distance = _hamming_distance(ref_bits, comp_bits)

            if distance <= threshold:
                similar_files.append((comp_path, comp_iscc, distance))
                processed.add(comp_path)

        # If this file has similar files, output the group
        if similar_files:
            # Add blank line between groups (except before first group)
            if group_count > 0:
                if not zero:
                    click.echo(file=output_file)

            group_count += 1

            # Output reference file
            _output_checksum(ref_iscc, ref_path, tag, zero, output_file)
            processed.add(ref_path)

            # Sort similar files by hamming distance (ascending)
            similar_files.sort(key=lambda x: x[2])

            # Output similar files with distance indicator
            for sim_path, sim_iscc, distance in similar_files:
                normalized_sim_path = _normalize_path_display(sim_path)
                if tag:
                    output = f"  ~{distance:02d} ISCC-SUM ({normalized_sim_path}) = {sim_iscc}"
                else:
                    output = f"  ~{distance:02d} {sim_iscc} *{normalized_sim_path}"

                click.echo(output, nl=not zero, file=output_file)
                if zero:
                    click.echo("\0", nl=False, file=output_file)

        # If this file has no similar files but hasn't been processed, output it alone
        elif ref_path not in processed:
            # Add blank line between groups (except before first group)
            if group_count > 0:
                if not zero:
                    click.echo(file=output_file)

            group_count += 1

            _output_checksum(ref_iscc, ref_path, tag, zero, output_file)
            processed.add(ref_path)


def _output_checksum(iscc, filepath, tag, zero, output_file=None):
    # type: (str, str, bool, bool, IO[Any] | None) -> None
    """Output a checksum in the specified format."""
    normalized_path = _normalize_path_display(filepath)
    if tag:
        output = f"ISCC-SUM ({normalized_path}) = {iscc}"
    else:
        output = f"{iscc} *{normalized_path}"

    click.echo(output, nl=not zero, file=output_file)
    if zero:
        click.echo("\0", nl=False, file=output_file)


if __name__ == "__main__":  # pragma: no cover
    cli()
