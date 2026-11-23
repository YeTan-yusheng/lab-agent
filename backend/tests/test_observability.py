import json
import logging
import sys

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from app.core.exceptions import BusinessException, register_exception_handlers
from app.core.logging import (
    ColorTextFormatter,
    JsonFormatter,
    RequestIdFilter,
    TextFormatter,
    request_id_ctx,
)
from app.core.middleware import RequestContextMiddleware


def build_app():
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)

    @app.get("/ok")
    def ok(request: Request):
        return {"request_id": request.state.request_id}

    @app.get("/boom")
    def boom():
        raise RuntimeError("boom-secret")

    @app.get("/business-409")
    def business_409():
        raise BusinessException("预约冲突", 409, error_code="RESERVATION_CONFLICT")

    @app.get("/forbidden")
    def forbidden():
        raise BusinessException("无权限", 403, error_code="FORBIDDEN")

    @app.get("/validation")
    def validation(q: int):
        return {"q": q}

    @app.get("/unauthorized")
    def unauthorized():
        raise HTTPException(status_code=401, detail="登录已失效")

    return app


@pytest.fixture()
def client():
    with TestClient(build_app(), raise_server_exceptions=False) as test_client:
        yield test_client


def _app_log_text(caplog):
    return "\n".join(
        record.getMessage()
        for record in caplog.records
        if record.name.startswith("app.")
    )


def test_request_id_from_header_is_echoed(client):
    response = client.get("/ok", headers={"X-Request-ID": "abc-123"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "abc-123"
    assert response.json()["request_id"] == "abc-123"


def test_invalid_request_id_is_replaced(client):
    response = client.get("/ok", headers={"X-Request-ID": "a" * 65})

    request_id = response.headers["X-Request-ID"]
    assert request_id != "a" * 65
    assert len(request_id) == 32
    assert response.json()["request_id"] == request_id


def test_generated_request_id_is_32_hex(client):
    response = client.get("/ok")

    request_id = response.headers["X-Request-ID"]
    assert len(request_id) == 32
    assert all(char in "0123456789abcdef" for char in request_id)
    assert response.json()["request_id"] == request_id


def test_unhandled_exception_returns_500_with_request_id_and_stack(client, caplog):
    caplog.set_level(logging.INFO)

    response = client.get("/boom", headers={"X-Request-ID": "req-boom"})

    assert response.status_code == 500
    body = response.json()
    assert body["code"] == 500
    assert body["error_code"] == "INTERNAL_ERROR"
    assert body["request_id"] == "req-boom"
    assert response.headers["X-Request-ID"] == "req-boom"

    record = next(r for r in caplog.records if r.msg == "unhandled_exception")
    assert record.levelno == logging.ERROR
    assert record.exc_info is not None
    assert record.request_id == "req-boom"
    assert record.status_code == 500


def test_business_409_logs_info_not_error(client, caplog):
    caplog.set_level(logging.INFO)

    response = client.get("/business-409")

    assert response.status_code == 409
    assert response.json()["error_code"] == "RESERVATION_CONFLICT"

    record = next(r for r in caplog.records if r.msg == "business_exception")
    assert record.levelno == logging.INFO
    assert not any(
        r.msg == "business_exception" and r.levelno >= logging.ERROR
        for r in caplog.records
    )


def test_forbidden_logs_warning(client, caplog):
    caplog.set_level(logging.INFO)

    response = client.get("/forbidden")

    assert response.status_code == 403
    record = next(r for r in caplog.records if r.msg == "business_exception")
    assert record.levelno == logging.WARNING


def test_validation_error_does_not_log_input(client, caplog):
    caplog.set_level(logging.INFO)

    response = client.get("/validation?q=not-int")

    assert response.status_code == 422
    assert response.json()["error_code"] == "VALIDATION_ERROR"
    assert "not-int" not in _app_log_text(caplog)
    record = next(r for r in caplog.records if r.msg == "validation_failed")
    assert record.levelno == logging.WARNING


def test_access_log_omits_query_string(client, caplog):
    caplog.set_level(logging.INFO)

    response = client.get("/ok?token=topsecret")

    assert response.status_code == 200
    record = next(r for r in caplog.records if r.msg == "request_completed")
    assert record.method == "GET"
    assert record.path == "/ok"
    assert record.status_code == 200
    assert record.duration_ms >= 0
    assert record.request_id == response.headers["X-Request-ID"]
    assert "topsecret" not in _app_log_text(caplog)


def test_unauthorized_keeps_data_null(client):
    response = client.get("/unauthorized", headers={"X-Request-ID": "req-401"})

    assert response.status_code == 401
    body = response.json()
    assert body["data"] is None
    assert body["request_id"] == "req-401"
    assert response.headers["X-Request-ID"] == "req-401"


def test_route_not_found_has_request_id(client):
    response = client.get("/missing", headers={"X-Request-ID": "req-404"})

    assert response.status_code == 404
    assert response.json()["request_id"] == "req-404"
    assert response.headers["X-Request-ID"] == "req-404"


def test_request_id_filter_preserves_explicit_value():
    token = request_id_ctx.set("ctx-id")
    try:
        explicit = logging.LogRecord(
            "test", logging.INFO, __file__, 1, "hello", (), None
        )
        explicit.request_id = "explicit-id"
        RequestIdFilter().filter(explicit)
        assert explicit.request_id == "explicit-id"

        implicit = logging.LogRecord(
            "test", logging.INFO, __file__, 1, "hello", (), None
        )
        RequestIdFilter().filter(implicit)
        assert implicit.request_id == "ctx-id"
    finally:
        request_id_ctx.reset(token)


def test_text_formatter_includes_request_id_and_extras():
    record = logging.LogRecord(
        "app.test", logging.INFO, __file__, 10, "reservation_created", (), None
    )
    record.request_id = "req-format"
    record.reservation_id = 12

    text = TextFormatter().format(record)

    assert "[req-format]" in text
    assert "reservation_id=12" in text


class _TTY:
    def isatty(self):
        return True


class _NoTTY:
    def isatty(self):
        return False


def test_color_formatter_colors_level_on_tty():
    record = logging.LogRecord(
        "app.test", logging.WARNING, __file__, 10, "slow", (), None
    )
    record.request_id = "req-color"

    text = ColorTextFormatter(enabled=True, stream=_TTY()).format(record)

    assert "\033[33mWARNING\033[0m" in text
    assert "[req-color]" in text


def test_color_formatter_is_plain_without_tty():
    record = logging.LogRecord(
        "app.test", logging.ERROR, __file__, 10, "failed", (), None
    )
    record.request_id = "req-plain"

    text = ColorTextFormatter(enabled=True, stream=_NoTTY()).format(record)

    assert "\033[" not in text
    assert "ERROR" in text


def test_json_formatter_includes_request_id_and_exception():
    try:
        raise ValueError("bad value")
    except ValueError:
        exc_info = sys.exc_info()

    record = logging.LogRecord(
        "app.test", logging.ERROR, __file__, 10, "unhandled_exception", (), exc_info
    )
    record.request_id = "req-json"
    record.status_code = 500

    payload = json.loads(JsonFormatter().format(record))

    assert payload["request_id"] == "req-json"
    assert payload["level"] == "ERROR"
    assert payload["status_code"] == 500
    assert "ValueError: bad value" in payload["exception"]