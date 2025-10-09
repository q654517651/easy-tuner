"""
异常处理模块（统一错误响应约定）
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from typing import Any, Optional
import logging
import traceback


logger = logging.getLogger(__name__)


class APIException(Exception):
    """API 层通用异常基类（前端友好响应）。"""

    status_code: int = 400
    error: str = "ApplicationError"  # 短码，默认由类名推导

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        detail: Any = None,
        error_code: Optional[str] = None,
        error: Optional[str] = None,
    ):
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.detail = detail
        self.error_code = error_code
        if error is not None:
            self.error = error
        else:
            # 根据类名推导短码（去除 Error/Exception 后缀）
            name = self.__class__.__name__
            for suf in ("Error", "Exception"):
                if name.endswith(suf):
                    name = name[: -len(suf)]
                    break
            self.error = name or "ApplicationError"
        super().__init__(message)


class DatasetNotFoundError(APIException):
    def __init__(self, message: Optional[str] = None, detail: Any = None, error_code: Optional[str] = None):
        super().__init__(message or "Dataset not found", status_code=404, detail=detail, error_code=error_code, error="DatasetNotFound")


class TrainingNotFoundError(APIException):
    def __init__(self, message: Optional[str] = None, detail: Any = None, error_code: Optional[str] = None):
        super().__init__(message or "Training task not found", status_code=404, detail=detail, error_code=error_code, error="TrainingNotFound")


class ValidationError(APIException):
    def __init__(self, message: str, detail: Any = None, error_code: Optional[str] = None):
        super().__init__(message, status_code=400, detail=detail, error_code=error_code, error="ValidationError")


class LabelingError(APIException):
    def __init__(self, message: str, detail: Any = None, error_code: Optional[str] = None):
        super().__init__(message, status_code=500, detail=detail, error_code=error_code, error="LabelingError")


class TrainingError(APIException):
    def __init__(self, message: str, detail: Any = None, error_code: Optional[str] = None):
        super().__init__(message, status_code=500, detail=detail, error_code=error_code, error="TrainingError")


def setup_exception_handlers(app: FastAPI):
    """安装全局异常处理器，输出统一响应结构。"""

    @app.exception_handler(APIException)
    async def api_exception_handler(request: Request, exc: APIException):
        logger.error("APIException: %s", exc.message)
        content = {
            "error": getattr(exc, "error", "ApplicationError"),
            "message": exc.message,
            "detail": exc.detail,
            "type": "application_error",
        }
        if getattr(exc, "error_code", None):
            content["error_code"] = exc.error_code
        return JSONResponse(status_code=exc.status_code, content=content)

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": "HTTPError",
                "message": exc.detail,
                "detail": None,
                "type": "application_error",
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "error": "ValidationError",
                "message": "请求参数校验失败",
                "detail": exc.errors(),
                "type": "application_error",
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        logger.error("未处理异常: %s", str(exc))
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={
                "error": "InternalServerError",
                "message": "服务器内部错误",
                "detail": str(exc) if getattr(app, "debug", False) else None,
                "type": "application_error",
            },
        )

