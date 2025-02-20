import os
import tempfile
from unittest.mock import patch

import pytest

from reconcile.quay_mirror import (
    CONTROL_FILE_NAME,
    QuayMirror,
)

NOW = 1662124612.995397


@patch("reconcile.utils.gql.get_api", autospec=True)
@patch("reconcile.queries.get_app_interface_settings", return_value={})
class TestControlFile:
    def test_check_compare_tags_no_control_file(self, mock_gql, mock_settings):
        assert QuayMirror.check_compare_tags_elapsed_time("/no-such-file", 100)

    @patch("time.time", return_value=NOW)
    def test_check_compare_tags_with_file(self, mock_gql, mock_settings, mock_time):
        with tempfile.NamedTemporaryFile() as fp:
            fp.write(str(NOW - 100.0).encode())
            fp.seek(0)

            assert QuayMirror.check_compare_tags_elapsed_time(fp.name, 10)
            assert not QuayMirror.check_compare_tags_elapsed_time(fp.name, 1000)

    def test_control_file_dir_does_not_exist(self, mock_gql, mock_settings):
        with pytest.raises(FileNotFoundError):
            QuayMirror(control_file_dir="/no-such-dir")

    def test_control_file_path_from_given_dir(self, mock_gql, mock_settings):
        with tempfile.TemporaryDirectory() as tmp_dir_name:
            qm = QuayMirror(control_file_dir=tmp_dir_name)
            assert qm.control_file_path == os.path.join(tmp_dir_name, CONTROL_FILE_NAME)


@patch("reconcile.utils.gql.get_api", autospec=True)
@patch("reconcile.queries.get_app_interface_settings", return_value={})
@patch("time.time", return_value=NOW)
class TestIsCompareTags:
    def setup_method(self):
        self.tmp_dir = (
            tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        )
        with open(os.path.join(self.tmp_dir.name, CONTROL_FILE_NAME), "w") as fh:
            fh.write(str(NOW - 100.0))

    def teardown_method(self):
        self.tmp_dir.cleanup()

    # Last run was in NOW - 100s, we run compare tags every 10s.
    def test_is_compare_tags_elapsed(self, mock_gql, mock_settings, mock_time):
        qm = QuayMirror(control_file_dir=self.tmp_dir.name, compare_tags_interval=10)
        assert qm.is_compare_tags

    # Same as before, but now we force no compare with the option.
    def test_is_compare_tags_force_no_compare(self, mock_gql, mock_settings, mock_time):
        qm = QuayMirror(
            control_file_dir=self.tmp_dir.name,
            compare_tags_interval=10,
            compare_tags=False,
        )
        assert not qm.is_compare_tags

    # Last run was in NOW - 100s, we run compare tags every 1000s.
    def test_is_compare_tags_not_elapsed(self, mock_gql, mock_settings, mock_time):
        qm = QuayMirror(control_file_dir=self.tmp_dir.name, compare_tags_interval=1000)
        assert not qm.is_compare_tags

    # Same as before, but now we force compare with the option.
    def test_is_compare_tags_force_compare(self, mock_gql, mock_settings, mock_time):
        qm = QuayMirror(
            control_file_dir=self.tmp_dir.name,
            compare_tags_interval=1000,
            compare_tags=True,
        )
        assert qm.is_compare_tags


@pytest.mark.parametrize(
    "tags, tags_exclude, candidate, result",
    [
        # Tags include tests.
        (["^sha256-.+sig$", "^main-.+"], None, "main-755781cc", True),
        (["^sha256-.+sig$", "^main-.+"], None, "sha256-8b5.sig", True),
        (["^sha256-.+sig$", "^main-.+"], None, "1.2.3", False),
        # Tags exclude tests.
        (None, ["^sha256-.+sig$", "^main-.+"], "main-755781cc", False),
        (None, ["^sha256-.+sig$", "^main-.+"], "sha256-8b5.sig", False),
        # When both includes and excludes are explicitly given, includes take precedence.
        (
            ["^sha256-.+sig$", "^main-.+"],
            ["^sha256-.+sig$", "^main-.+"],
            "main-755781cc",
            True,
        ),
        (
            ["^sha256-.+sig$", "^main-.+"],
            ["^sha256-.+sig$", "^main-.+"],
            "sha256-8b5.sig",
            True,
        ),
    ],
)
def test_sync_tag(tags, tags_exclude, candidate, result):
    assert QuayMirror.sync_tag(tags, tags_exclude, candidate) == result
