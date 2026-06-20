import worker_entrypoint


def test_parse_autoscale_valid_pair():
    assert worker_entrypoint._parse_autoscale("10,2") == (10, 2)
    assert worker_entrypoint._parse_autoscale(" 8, 1 ") == (8, 1)


def test_parse_autoscale_rejects_invalid_values():
    assert worker_entrypoint._parse_autoscale("") is None
    assert worker_entrypoint._parse_autoscale("10") is None
    assert worker_entrypoint._parse_autoscale("a,1") is None
    assert worker_entrypoint._parse_autoscale("1,a") is None
    assert worker_entrypoint._parse_autoscale("0,0") is None
    assert worker_entrypoint._parse_autoscale("2,3") is None
    assert worker_entrypoint._parse_autoscale("-1,0") is None


def test_celery_pool_args_prefers_valid_autoscale(monkeypatch):
    monkeypatch.setenv("CELERY_AUTOSCALE", "12,3")
    monkeypatch.setenv("CELERY_CONCURRENCY", "99")

    assert worker_entrypoint._celery_pool_args() == ["--autoscale", "12,3"]


def test_celery_pool_args_falls_back_to_concurrency_when_autoscale_invalid(
    monkeypatch, capsys
):
    monkeypatch.setenv("CELERY_AUTOSCALE", "not-valid")
    monkeypatch.setenv("CELERY_CONCURRENCY", "7")

    assert worker_entrypoint._celery_pool_args() == ["--concurrency", "7"]
    stderr = capsys.readouterr().err
    assert "Ignoring invalid CELERY_AUTOSCALE" in stderr
