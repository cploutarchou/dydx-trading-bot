from starlette.requests import Request

from src.api.server import _is_expected_strategy_runtime_probe_404


def build_request(path: str, method: str = "GET") -> Request:
    return Request(
        {
            "type": "http",
            "method": method,
            "path": path,
            "headers": [],
            "query_string": b"",
        }
    )


def test_expected_strategy_runtime_probe_404_matches_root_and_stats_paths():
    assert (
            _is_expected_strategy_runtime_probe_404(
                build_request("/api/v1/bots/strategy-1-5"), 404
            )
            is True
    )
    assert (
            _is_expected_strategy_runtime_probe_404(
                build_request("/api/v1/bots/strategy-1-5/stats"), 404
            )
            is True
    )


def test_expected_strategy_runtime_probe_404_rejects_non_strategy_paths_and_statuses():
    assert (
            _is_expected_strategy_runtime_probe_404(
                build_request("/api/v1/bots/manual-bot-1/stats"), 404
            )
            is False
    )
    assert (
            _is_expected_strategy_runtime_probe_404(
                build_request("/api/v1/bots/strategy-1-5/restart", method="POST"), 404
            )
            is False
    )
    assert (
            _is_expected_strategy_runtime_probe_404(
                build_request("/api/v1/bots/strategy-1-5/stats"), 400
            )
            is False
    )
