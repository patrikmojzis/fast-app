from fast_app.decorators.retry_decorator import retry


def test_retry_decorator_eventually_succeeds():
    calls = {"count": 0}

    @retry([ValueError], max_retries=2)
    def flaky():
        calls["count"] += 1
        if calls["count"] < 3:
            raise ValueError("fail")
        return "ok"

    assert flaky() == "ok"
    assert calls["count"] == 3
