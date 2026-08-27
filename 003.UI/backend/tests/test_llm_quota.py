from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from services import llm_quota


def test_default_limits_by_member_level():
    assert llm_quota.default_token_limit("free") == 200000
    assert llm_quota.default_token_limit("premium") == 2000000
    assert llm_quota.default_token_limit(None) == 200000


def test_parse_usage_prefers_api_usage_object():
    usage = llm_quota.parse_usage_from_response({
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
    })
    assert usage["total_tokens"] == 30
    assert usage["prompt_tokens"] == 10


def test_parse_usage_estimates_when_missing():
    usage = llm_quota.parse_usage_from_response({}, prompt_hint="abcd", completion_hint="efgh")
    assert usage["total_tokens"] >= 1


def test_assert_within_quota_blocks_when_exhausted():
    db = MagicMock()
    user = SimpleNamespace(id=7, member_level="free")
    db.query.return_value.filter.return_value.first.return_value = user
    with patch.object(llm_quota, "get_quota_snapshot", return_value={
        "tokens_used": 200000,
        "token_limit": 200000,
        "user_id": 7,
    }):
        try:
            llm_quota.assert_within_quota(db, 7)
            assert False, "expected QuotaExceededError"
        except llm_quota.QuotaExceededError as exc:
            assert "用尽" in str(exc)


def test_assert_within_quota_allows_remaining():
    db = MagicMock()
    user = SimpleNamespace(id=7, member_level="free")
    db.query.return_value.filter.return_value.first.return_value = user
    with patch.object(llm_quota, "get_quota_snapshot", return_value={
        "tokens_used": 10,
        "token_limit": 200000,
        "user_id": 7,
    }):
        snap = llm_quota.assert_within_quota(db, 7)
    assert snap["tokens_used"] == 10


def test_window_start_is_rolling_days():
    now = datetime(2026, 8, 27, 12, 0, 0)
    start = llm_quota.window_start(now)
    assert start.replace(tzinfo=None) == now - timedelta(days=30)
