"""Unit tests for version check integration in skill_helpers.py"""

import json
import os
import sys
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


# We test the version check functions directly, not the full skill_helpers
# since that requires ChromaDB. Import the module and mock adapters.


class TestCheckVersionCache:
    """Test _check_version_cache with various cache states."""

    def test_missing_cache_returns_none(self, tmp_path):
        """Cache file doesn't exist → returns None."""
        from memoria.skill_helpers import _check_version_cache, _VERSION_CACHE_PATH

        with patch.object(
            sys.modules["memoria.skill_helpers"],
            "_VERSION_CACHE_PATH",
            tmp_path / ".version-cache",
        ):
            result = _check_version_cache()
            assert result is None

    def test_fresh_cache_returns_data(self, tmp_path):
        """Cache file is fresh (within TTL) → returns data."""
        from memoria.skill_helpers import _check_version_cache

        cache_file = tmp_path / ".version-cache"
        cache_data = {
            "latest_version": "1.2.0",
            "current_version": "1.0.0",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "cache_ttl_hours": 24,
            "update_available": True,
            "notification_shown": False,
            "check_error": None,
        }
        cache_file.write_text(json.dumps(cache_data))

        with patch.object(
            sys.modules["memoria.skill_helpers"],
            "_VERSION_CACHE_PATH",
            cache_file,
        ):
            result = _check_version_cache()
            assert result is not None
            assert result["latest_version"] == "1.2.0"
            assert result["update_available"] is True

    def test_stale_cache_returns_none(self, tmp_path):
        """Cache file is stale (beyond TTL) → returns None."""
        from memoria.skill_helpers import _check_version_cache

        cache_file = tmp_path / ".version-cache"
        stale_time = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        cache_data = {
            "latest_version": "1.2.0",
            "current_version": "1.0.0",
            "checked_at": stale_time,
            "cache_ttl_hours": 24,
            "update_available": True,
            "notification_shown": False,
            "check_error": None,
        }
        cache_file.write_text(json.dumps(cache_data))

        with patch.object(
            sys.modules["memoria.skill_helpers"],
            "_VERSION_CACHE_PATH",
            cache_file,
        ):
            result = _check_version_cache()
            assert result is None

    def test_corrupt_cache_returns_none(self, tmp_path):
        """Cache file has invalid JSON → returns None gracefully."""
        from memoria.skill_helpers import _check_version_cache

        cache_file = tmp_path / ".version-cache"
        cache_file.write_text("not valid json {{{")

        with patch.object(
            sys.modules["memoria.skill_helpers"],
            "_VERSION_CACHE_PATH",
            cache_file,
        ):
            result = _check_version_cache()
            assert result is None


class TestShouldNotifyUpdate:
    """Test _should_notify_update with various version combinations."""

    def test_no_cache_no_notify(self, tmp_path):
        """No cache → no notification."""
        from memoria.skill_helpers import _should_notify_update

        with patch.object(
            sys.modules["memoria.skill_helpers"],
            "_VERSION_CACHE_PATH",
            tmp_path / ".version-cache",
        ):
            should, version = _should_notify_update()
            assert should is False

    def test_update_available_notify(self, tmp_path):
        """Update available + not yet shown → notify."""
        from memoria.skill_helpers import _should_notify_update

        cache_file = tmp_path / ".version-cache"
        cache_data = {
            "latest_version": "2.0.0",
            "current_version": "1.0.0",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "cache_ttl_hours": 24,
            "update_available": True,
            "notification_shown": False,
            "check_error": None,
        }
        cache_file.write_text(json.dumps(cache_data))

        with patch.object(
            sys.modules["memoria.skill_helpers"],
            "_VERSION_CACHE_PATH",
            cache_file,
        ):
            should, version = _should_notify_update()
            assert should is True
            assert version == "2.0.0"

    def test_notification_already_shown(self, tmp_path):
        """Update available but already shown → no notification."""
        from memoria.skill_helpers import _should_notify_update

        cache_file = tmp_path / ".version-cache"
        cache_data = {
            "latest_version": "2.0.0",
            "current_version": "1.0.0",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "cache_ttl_hours": 24,
            "update_available": True,
            "notification_shown": True,
            "check_error": None,
        }
        cache_file.write_text(json.dumps(cache_data))

        with patch.object(
            sys.modules["memoria.skill_helpers"],
            "_VERSION_CACHE_PATH",
            cache_file,
        ):
            should, version = _should_notify_update()
            assert should is False

    def test_no_update_available(self, tmp_path):
        """Same version → no notification."""
        from memoria.skill_helpers import _should_notify_update

        cache_file = tmp_path / ".version-cache"
        cache_data = {
            "latest_version": "1.0.0",
            "current_version": "1.0.0",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "cache_ttl_hours": 24,
            "update_available": False,
            "notification_shown": False,
            "check_error": None,
        }
        cache_file.write_text(json.dumps(cache_data))

        with patch.object(
            sys.modules["memoria.skill_helpers"],
            "_VERSION_CACHE_PATH",
            cache_file,
        ):
            should, version = _should_notify_update()
            assert should is False


class TestMarkNotificationShown:
    """Test _mark_notification_shown flag persistence."""

    def test_marks_shown_in_cache(self, tmp_path):
        """After marking, notification_shown should be True in file."""
        from memoria.skill_helpers import _mark_notification_shown

        cache_file = tmp_path / ".version-cache"
        cache_data = {
            "latest_version": "2.0.0",
            "current_version": "1.0.0",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "cache_ttl_hours": 24,
            "update_available": True,
            "notification_shown": False,
            "check_error": None,
        }
        cache_file.write_text(json.dumps(cache_data))

        with patch.object(
            sys.modules["memoria.skill_helpers"],
            "_VERSION_CACHE_PATH",
            cache_file,
        ):
            _mark_notification_shown()

        updated = json.loads(cache_file.read_text())
        assert updated["notification_shown"] is True

    def test_missing_cache_no_error(self, tmp_path):
        """Missing cache file → no error raised."""
        from memoria.skill_helpers import _mark_notification_shown

        with patch.object(
            sys.modules["memoria.skill_helpers"],
            "_VERSION_CACHE_PATH",
            tmp_path / ".nonexistent-cache",
        ):
            _mark_notification_shown()  # Should not raise


class TestUpdateVersionCache:
    """Test _update_version_cache with mocked subprocess."""

    def test_gh_not_available(self, tmp_path):
        """gh CLI not installed → graceful failure, no error."""
        from memoria.skill_helpers import _update_version_cache
        import subprocess

        with patch("subprocess.run", side_effect=FileNotFoundError("gh not found")):
            with patch.object(
                sys.modules["memoria.skill_helpers"],
                "_VERSION_CACHE_PATH",
                tmp_path / ".version-cache",
            ):
                _update_version_cache()  # Should not raise

        assert not (tmp_path / ".version-cache").exists()

    def test_network_timeout(self, tmp_path):
        """Network timeout → graceful failure."""
        from memoria.skill_helpers import _update_version_cache
        import subprocess

        with patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired("gh", 5),
        ):
            with patch.object(
                sys.modules["memoria.skill_helpers"],
                "_VERSION_CACHE_PATH",
                tmp_path / ".version-cache",
            ):
                _update_version_cache()  # Should not raise

    def test_successful_check_writes_cache(self, tmp_path):
        """Successful gh call → writes cache file."""
        from memoria.skill_helpers import _update_version_cache

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "v2.0.0\n"

        cache_file = tmp_path / ".version-cache"

        with patch("subprocess.run", return_value=mock_result):
            with patch.object(
                sys.modules["memoria.skill_helpers"],
                "_VERSION_CACHE_PATH",
                cache_file,
            ):
                with patch.object(
                    sys.modules["memoria.skill_helpers"],
                    "MEMORIA_ROOT",
                    tmp_path,
                ):
                    # Create a VERSION file
                    (tmp_path / "VERSION").write_text("1.0.0")
                    _update_version_cache()

        assert cache_file.exists()
        data = json.loads(cache_file.read_text())
        assert data["latest_version"] == "2.0.0"
        assert data["current_version"] == "1.0.0"
        assert data["update_available"] is True
