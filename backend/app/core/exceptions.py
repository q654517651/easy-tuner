"""
异常处理模块
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging
import traceback

logger = logging.getLogger(__name__)


class APIException(Exception):
    """API基础异常类"""
    def __init__(self, message: str, status_code: int = 500, detail: str = None):
        self.message = message
        self.status_code = status_code
        self.detail = detail
        super().__init__(message)


class DatasetNotFoundError(APIException):
    """数据集未找到异常"""
    def __init__(self, dataset_id: str):
        super().__init__(f"数据集未找到: {dataset_id}", 404)


class TrainingTaskNotFoundError(APIException):
    """训练任务未找到异常"""
    def __init__(self, task_id: str):
        super().__init__(f"训练任务未找到: {task_id}", 404)


class ValidationError(APIException):
    """数据验证异常"""
    def __init__(self, message: str, detail: str = None):
        super().__init__(message, 400, detail)


class LabelingError(APIException):
    """打标服务异常"""
    def __init__(self, message: str, detail: str = None):
        super().__init__(message, 500, detail)


class TrainingError(APIException):
    """训练异常"""
    def __init__(self, message: str, detail: str = None):
        super().__init__(message, 500, detail)


def setup_exception_handlers(app: FastAPI):
    """设置全局异常处理器"""
    
    @app.exception_handler(APIException)
    async def api_exception_handler(request: Request, exc: APIException):
        """处理自定义API异常"""
        logger.error(f"API异常: {exc.message}")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": True,
                "message": exc.message,
                "detail": exc.detail,
                "type": exc.__class__.__name__
            }
        )
    
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """处理HTTP异常"""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": True,
                "message": exc.detail,
                "type": "HTTPException"
            }
        )
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """处理请求验证异常"""
        return JSONResponse(
            status_code=422,
            content={
                "error": True,
                "message": "请求数据验证失败",
                "detail": exc.errors(),
                "type": "ValidationError"
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """处理未捕获的异常"""
        logger.error(f"未处理异常: {str(exc)}")
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={
                "error": True,
                "message": "服务器内部错误",
                "detail": str(exc) if app.debug else None,
                "type": "InternalServerError"
            }
        )