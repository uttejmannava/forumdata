"""Tests for error taxonomy."""

from forum_schemas.models.errors import ErrorCode, ForumError, WarningCode


class TestErrorCodes:
    def test_critical_error_count(self) -> None:
        """bible.md §12.3 defines 10 critical error codes."""
        assert len(ErrorCode) == 10

    def test_warning_count(self) -> None:
        """bible.md §12.3 defines 7 non-critical warning codes."""
        assert len(WarningCode) == 7


class TestForumError:
    def test_create_error(self) -> None:
        err = ForumError(code=ErrorCode.SOURCE_UNAVAILABLE, message="Site returned 503")
        assert err.code == ErrorCode.SOURCE_UNAVAILABLE

    def test_create_warning(self) -> None:
        warn = ForumError(code=WarningCode.STALE_DATA, message="Data unchanged", context={"last_changed": "2025-03-14"})
        assert warn.context["last_changed"] == "2025-03-14"
