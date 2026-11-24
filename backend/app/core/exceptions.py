import logging
import uuid
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import request_id_ctx
from app.core.permissions import RoleValidationError
from app.core.response import ErrorResponse

logger = logging.getLogger(__name__)


class BusinessException(Exception):
    """自定义的业务异常"""

    def __init__(self, message: str, code: int = 400, error_code: str | None = None):
        self.message = message
        self.code = code
        self.error_code = error_code
        super().__init__(message)


def _http_status(code: int, default: int) -> int:
    return code if 400 <= code <= 599 else default


def _request_id(request: Request) -> str:
    request_id = (
        getattr(request.state, "request_id", None) or request_id_ctx.get()
    )
    if not request_id:
        request_id = uuid.uuid4().hex
        request.state.request_id = request_id
    return request_id


def _error(
    status: int,
    code: int,
    message: str,
    request: Request,
    error_code: str | None = None,
) -> JSONResponse:
    request_id = _request_id(request)
    return JSONResponse(
        status_code=status,
        content=ErrorResponse(
            code=code,
            message=message,
            error_code=error_code,
            request_id=request_id,
        ).model_dump(),
        headers={"X-Request-ID": request_id},
    )


def _log_failure(
    request: Request,
    exc: Exception,
    status: int,
    event: str,
    error_code: str | None = None,
) -> None:
    extra = {
        "request_id": _request_id(request),
        "method": request.method,
        "path": request.url.path,
        "status_code": status,
        "user_id": getattr(request.state, "user_id", None),
        "error_code": error_code,
    }
    if status >= 500:
        logger.error(
            event,
            exc_info=(type(exc), exc, exc.__traceback__),
            extra=extra,
        )
    elif status in (401, 403):
        logger.warning(event, extra=extra)
    else:
        logger.info(event, extra=extra)


async def role_validation_exception_handler(request: Request, exc: RoleValidationError):
    """角色校验异常处理器"""
    status_code = _http_status(exc.code, 422)
    _log_failure(
        request, exc, status_code, "role_validation_failed", "ROLE_VALIDATION_ERROR"
    )
    return _error(
        status_code,
        exc.code,
        exc.message,
        request,
        "ROLE_VALIDATION_ERROR",
    )


async def bussiness_excpetion_handler(request: Request, exc: BusinessException):
    """自定义业务异常处理器"""
    status_code = _http_status(exc.code, 400)
    _log_failure(request, exc, status_code, "business_exception", exc.error_code)
    return _error(status_code, exc.code, exc.message, request, exc.error_code)


async def http_excpetion_handler(request: Request, exc: StarletteHTTPException):
    """Http异常处理器"""
    status_code = exc.status_code
    _log_failure(request, exc, status_code, "http_exception")
    message = "服务器内部错误" if status_code >= 500 else exc.detail
    return _error(status_code, status_code, message, request)


async def validation_excpetion_handler(request: Request, exc: RequestValidationError):
    """参数异常处理器"""
    errors = [
        {
            "loc": [str(item) for item in error.get("loc", [])],
            "type": error.get("type"),
            "msg": error.get("msg"),
        }
        for error in exc.errors()
    ]
    logger.warning(
        "validation_failed",
        extra={
            "request_id": _request_id(request),
            "method": request.method,
            "path": request.url.path,
            "status_code": 422,
            "error_count": len(errors),
            "error_fields": ",".join(
                ".".join(error["loc"]) for error in errors
            ),
        },
    )
    return _error(
        422,
        422,
        "请求参数校验错误",
        request,
        "VALIDATION_ERROR",
    )


async def global_excpetion_handler(request: Request, exc: Exception):
    """全局异常处理器"""
    _log_failure(request, exc, 500, "unhandled_exception", "INTERNAL_ERROR")
    return _error(500, 500, "服务器内部错误", request, "INTERNAL_ERROR")


def register_exception_handlers(app) -> None:
    app.add_exception_handler(BusinessException, bussiness_excpetion_handler)
    # FastAPI 的 HTTPException 是 Starlette 的子类；注册基类才能接住路由层 404
    app.add_exception_handler(StarletteHTTPException, http_excpetion_handler)
    app.add_exception_handler(RequestValidationError, validation_excpetion_handler)
    app.add_exception_handler(RoleValidationError, role_validation_exception_handler)
    # 全局兜底必须最后注册
    app.add_exception_handler(Exception, global_excpetion_handler)
