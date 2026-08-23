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


def test_worker_entrypoint_defaults_to_all_operational_celery_queues(monkeypatch):
    argv = []

    def _fake_celery_main():
        argv.extend(worker_entrypoint.sys.argv)
        return 0

    monkeypatch.setenv("WORKER_MODE", "celery")
    monkeypatch.delenv("CELERY_QUEUES", raising=False)
    monkeypatch.setattr("celery.__main__.main", _fake_celery_main)

    assert worker_entrypoint.main() == 0
    assert "--queues" in argv
    assert argv[argv.index("--queues") + 1] == ("backtests,default,scheduled")
