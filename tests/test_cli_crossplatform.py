# Test cross-platform compatibility for iscc-sum CLI

import os
import platform
import sys
import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from iscc_sum.cli import cli


@pytest.fixture
def runner():
    # type: () -> CliRunner
    """Create a CLI runner."""
    return CliRunner()


class TestCrossPlatformCompatibility:
    """Test CLI behavior across different platforms."""

    def test_unicode_filename_handling(self, runner, tmp_path):
        # type: (CliRunner, Path) -> None
        """Test handling of Unicode filenames."""
        # Create files with various Unicode characters
        unicode_files = [
            "test_文件.txt",  # Chinese characters
            "test_файл.txt",  # Cyrillic characters
            "test_αρχείο.txt",  # Greek characters
            "test_ملف.txt",  # Arabic characters
            "test_emoji_😀.txt",  # Emoji
            "test_mixed_文件_файл.txt",  # Mixed scripts
        ]

        created_files = []
        for filename in unicode_files:
            try:
                filepath = tmp_path / filename
                filepath.write_bytes(b"test content")
                created_files.append(str(filepath))
            except (OSError, UnicodeError):
                # Skip files that can't be created on this platform
                continue

        if not created_files:
            pytest.skip("Unicode filenames not supported on this platform")

        # Test checksum generation
        result = runner.invoke(cli, created_files)
        assert result.exit_code == 0
        assert len(result.output.strip().split("\n")) == len(created_files)

    def test_special_characters_in_filenames(self, runner, tmp_path):
        # type: (CliRunner, Path) -> None
        """Test handling of special characters in filenames."""
        # Create files with special characters (platform-dependent)
        special_files = []

        # Characters that should work on all platforms
        safe_special = ["test file.txt", "test-file.txt", "test_file.txt", "test.file.txt"]

        for filename in safe_special:
            filepath = tmp_path / filename
            filepath.write_bytes(b"test content")
            special_files.append(str(filepath))

        # Platform-specific special characters
        if platform.system() != "Windows":
            # Unix-like systems allow more special characters
            unix_special = ["test:file.txt", "test|file.txt", 'test"file.txt']
            for filename in unix_special:
                try:
                    filepath = tmp_path / filename
                    filepath.write_bytes(b"test content")
                    special_files.append(str(filepath))
                except OSError:
                    # Skip if not allowed
                    pass

        # Test checksum generation
        result = runner.invoke(cli, special_files)
        assert result.exit_code == 0
        assert len(result.output.strip().split("\n")) == len(special_files)

    def test_path_separator_handling(self, runner, tmp_path):
        # type: (CliRunner, Path) -> None
        """Test correct handling of path separators."""
        # Create nested directory structure
        nested_dir = tmp_path / "dir1" / "dir2" / "dir3"
        nested_dir.mkdir(parents=True)

        # Create test file
        test_file = nested_dir / "test.txt"
        test_file.write_bytes(b"test content")

        # Test with native path
        native_path = str(test_file)
        result = runner.invoke(cli, [native_path])
        assert result.exit_code == 0

        # On all platforms, output should use forward slashes
        normalized_path = native_path.replace("\\", "/")
        assert normalized_path in result.output

        # Ensure no backslashes in output (cross-platform consistency)
        assert "\\" not in result.output

        # Test with Path object (should work through Click's path handling)
        result = runner.invoke(cli, [str(test_file)])
        assert result.exit_code == 0

    def test_line_ending_handling(self, runner, tmp_path):
        # type: (CliRunner, Path) -> None
        """Test correct handling of different line endings."""
        # Create files with different line endings
        lf_file = tmp_path / "lf.txt"
        lf_file.write_bytes(b"line1\nline2\nline3\n")

        crlf_file = tmp_path / "crlf.txt"
        crlf_file.write_bytes(b"line1\r\nline2\r\nline3\r\n")

        cr_file = tmp_path / "cr.txt"
        cr_file.write_bytes(b"line1\rline2\rline3\r")

        # Files should produce same checksum if they have same binary content
        result_lf = runner.invoke(cli, [str(lf_file)])
        result_crlf = runner.invoke(cli, [str(crlf_file)])
        result_cr = runner.invoke(cli, [str(cr_file)])

        assert result_lf.exit_code == 0
        assert result_crlf.exit_code == 0
        assert result_cr.exit_code == 0

        # Extract checksums - they should be different since binary content differs
        checksum_lf = result_lf.output.split()[0]
        checksum_crlf = result_crlf.output.split()[0]
        checksum_cr = result_cr.output.split()[0]

        assert checksum_lf != checksum_crlf
        assert checksum_lf != checksum_cr
        assert checksum_crlf != checksum_cr

    def test_stdin_handling_crossplatform(self, runner):
        # type: (CliRunner) -> None
        """Test stdin handling across platforms."""
        # Test with binary input
        test_data = b"Test binary data \x00\x01\x02\x03"
        result = runner.invoke(cli, input=test_data)
        assert result.exit_code == 0
        assert "ISCC:" in result.output
        assert " *-" in result.output  # stdin is shown as "-"

    def test_long_path_handling(self, runner, tmp_path):
        # type: (CliRunner, Path) -> None
        """Test handling of very long file paths."""
        # Create a deeply nested directory structure
        current = tmp_path
        for i in range(20):  # Create 20 levels deep
            current = current / f"directory_level_{i:02d}"
            current.mkdir()

        # Create file at the deepest level
        deep_file = current / "deeply_nested_test_file_with_long_name.txt"
        deep_file.write_bytes(b"test content")

        # Test if we can handle the long path
        result = runner.invoke(cli, [str(deep_file)])

        if platform.system() == "Windows" and len(str(deep_file)) > 260:
            # Windows has path length limitations without extended path support
            if result.exit_code != 0:
                pytest.skip("Long paths not supported on this Windows configuration")

        assert result.exit_code == 0
        assert "ISCC:" in result.output

    def test_relative_vs_absolute_paths(self, runner, tmp_path):
        # type: (CliRunner, Path) -> None
        """Test handling of relative and absolute paths."""
        # Create test file
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"test content")

        # Test with absolute path
        abs_result = runner.invoke(cli, [str(test_file.absolute())])
        assert abs_result.exit_code == 0

        # Test with relative path using chdir

        original_cwd = os.getcwd()
        try:
            os.chdir(str(tmp_path))
            rel_result = runner.invoke(cli, ["test.txt"])
            assert rel_result.exit_code == 0
        finally:
            os.chdir(original_cwd)

        # Both should produce the same checksum
        abs_checksum = abs_result.output.split()[0]
        rel_checksum = rel_result.output.split()[0]
        assert abs_checksum == rel_checksum

    def test_verification_file_encoding(self, runner, tmp_path):
        # type: (CliRunner, Path) -> None
        """Test verification with different file encodings."""
        # Create test file
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"test content")

        # Generate checksum
        result = runner.invoke(cli, [str(test_file)])
        checksum_line = result.output.strip()

        # Create verification files with different encodings
        encodings = ["utf-8", "utf-16", "latin-1"]

        for encoding in encodings:
            verify_file = tmp_path / f"checksums_{encoding}.txt"
            try:
                verify_file.write_text(checksum_line, encoding=encoding)
            except (UnicodeError, LookupError):
                # Skip unsupported encodings
                continue

            # Verify - should work since CLI uses utf-8 by default
            if encoding == "utf-8":
                result = runner.invoke(cli, ["--check", str(verify_file)])
                assert result.exit_code == 0
                assert "OK" in result.output

    def test_zero_termination_crossplatform(self, runner, tmp_path):
        # type: (CliRunner, Path) -> None
        """Test zero-terminated output works correctly."""
        # Create test files
        files = []
        for i in range(3):
            f = tmp_path / f"test{i}.txt"
            f.write_bytes(f"content {i}".encode())
            files.append(str(f))

        # Test zero-terminated output
        result = runner.invoke(cli, ["--zero"] + files)
        assert result.exit_code == 0

        # Output should contain null bytes
        assert "\0" in result.output
        # Should have 3 null bytes (one per file)
        assert result.output.count("\0") == 3
        # Should not end with newline
        assert not result.output.endswith("\n")

    def test_binary_file_handling(self, runner, tmp_path):
        # type: (CliRunner, Path) -> None
        """Test handling of binary files with various content."""
        # Create binary files with different content
        binary_files = [
            ("null_bytes.bin", b"\x00" * 100),
            ("random_bytes.bin", bytes(range(256))),
            ("high_bytes.bin", bytes(range(128, 256)) * 10),
            ("mixed_content.bin", b"Text\x00Binary\xff\xfeContent"),
        ]

        created = []
        for filename, content in binary_files:
            filepath = tmp_path / filename
            filepath.write_bytes(content)
            created.append(str(filepath))

        # All binary files should be processed successfully
        result = runner.invoke(cli, created)
        assert result.exit_code == 0
        assert len(result.output.strip().split("\n")) == len(created)

    def test_symlink_handling(self, runner, tmp_path):
        # type: (CliRunner, Path) -> None
        """Test handling of symbolic links."""
        if platform.system() == "Windows":
            pytest.skip("Symlink test requires elevated privileges on Windows")

        # Create a regular file
        target_file = tmp_path / "target.txt"
        target_file.write_bytes(b"target content")

        # Create a symlink
        symlink = tmp_path / "link.txt"
        try:
            symlink.symlink_to(target_file)
        except OSError:
            pytest.skip("Symlinks not supported on this system")

        # Test both target and symlink
        target_result = runner.invoke(cli, [str(target_file)])
        symlink_result = runner.invoke(cli, [str(symlink)])

        assert target_result.exit_code == 0
        assert symlink_result.exit_code == 0

        # They should produce the same checksum
        target_checksum = target_result.output.split()[0]
        symlink_checksum = symlink_result.output.split()[0]
        assert target_checksum == symlink_checksum

    def test_case_sensitivity_handling(self, runner, tmp_path):
        # type: (CliRunner, Path) -> None
        """Test handling of case-sensitive vs case-insensitive filesystems."""
        # Create a file
        test_file = tmp_path / "TestFile.txt"
        test_file.write_bytes(b"test content")

        # Test with exact case
        result1 = runner.invoke(cli, [str(test_file)])
        assert result1.exit_code == 0

        # Test with different case
        different_case = tmp_path / "testfile.txt"
        result2 = runner.invoke(cli, [str(different_case)])

        # Behavior depends on filesystem
        if result2.exit_code == 0:
            # Case-insensitive filesystem (Windows, macOS by default)
            # Should produce same checksum
            checksum1 = result1.output.split()[0]
            checksum2 = result2.output.split()[0]
            assert checksum1 == checksum2
        else:
            # Case-sensitive filesystem (Linux)
            # File not found
            assert "No such file" in result2.output
