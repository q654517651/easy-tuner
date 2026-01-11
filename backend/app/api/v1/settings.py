"""
设置 API 路由：配置读取、保存与环境安装
"""

from fastapi import APIRouter, HTTPException, Response
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel
from typing import Dict, Any, Optional
from dataclasses import asdict
from pathlib import Path

from ...core.config import get_config, save_config, reload_config
from ...core.schema_manager import schema_manager
from ...utils.logger import log_info


router = APIRouter()


class AppSettings(BaseModel):
    musubi: Dict[str, Any]
    model_paths: Dict[str, Dict[str, Any]]
    labeling: Dict[str, Any]


def serialize_config() -> Dict[str, Any]:
    cfg = get_config()

    # 动态按 schema 导出 model_paths
    model_paths: Dict[str, Dict[str, Any]] = {}
    valid_paths = schema_manager.get_valid_paths()

    for path in valid_paths:
        if path.startswith("model_paths."):
            parts = path.split('.')
            if len(parts) == 3:  # model_paths.qwen_image.dit_path
                model_key, field_key = parts[1], parts[2]
                if model_key not in model_paths:
                    model_paths[model_key] = {}

                value = getattr(getattr(cfg.model_paths, model_key, object()), field_key, "")
                model_paths[model_key][field_key] = value

    # 获取所有已知的 provider，并填充默认值
    from ...core.labeling.providers.registry import PROVIDER_METADATA
    labeling_models = {}
    for provider_id, metadata in PROVIDER_METADATA.items():
        # 获取用户配置（如果有）
        user_config = cfg.labeling.models.get(provider_id, {})
        
        # 初始化该 provider 的配置，先填充所有字段的默认值
        provider_config = {}
        for field in metadata.config_fields:
            # 优先使用用户配置的值，如果没有则使用默认值
            if field.key in user_config:
                provider_config[field.key] = user_config[field.key]
            elif field.default is not None:
                provider_config[field.key] = field.default
        
        labeling_models[provider_id] = provider_config

    return {
        "musubi": asdict(cfg.musubi),
        "model_paths": model_paths,
        "labeling": {
            "default_prompt": cfg.labeling.default_prompt,
            "translation_prompt": cfg.labeling.translation_prompt,
            "selected_model": cfg.labeling.selected_model,
            "delay_between_calls": cfg.labeling.delay_between_calls,
            "models": labeling_models  # 确保所有 provider 都有默认空配置
        }
    }


@router.get("/settings")
async def get_settings():
    try:
        # 序列化配置（不再需要 musubi 版本信息）
        config_data = serialize_config()

        return {"success": True, "message": "配置获取成功", "data": config_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"配置获取失败: {str(e)}")


@router.get("/settings/model-paths/schema")
async def get_model_paths_schema():
    """获取模型路径 schema（含缓存）"""
    try:
        schema = schema_manager.get_schema()
        return {"success": True, "data": schema}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取 Schema 失败: {str(e)}")


@router.put("/settings/model-paths")
async def update_model_paths_settings(request: Dict[str, Any]):
    """更新模型路径设置 - 经过 schema 清洗与校验"""
    try:
        cleaned_settings = schema_manager.clean_config(request)

        cfg = get_config()

        # 更新 model_paths（动态更新）
        cleaned_model_paths = cleaned_settings.get("model_paths", {})
        if cleaned_model_paths and hasattr(cfg, 'model_paths'):
            for model_key, model_config in cleaned_model_paths.items():
                if isinstance(model_config, dict):
                    if model_key not in cfg.model_paths._data:
                        cfg.model_paths._data[model_key] = {}
                    # 更新字段值（包括 _groups）
                    for field_key, field_value in model_config.items():
                        cfg.model_paths._data[model_key][field_key] = field_value

        save_config(cfg)

        # 重新加载配置，刷新内存中的全局配置
        reload_config()

        # 刷新环境管理器中的workspace路径
        from ...core.environment import get_env_manager
        get_env_manager().refresh_from_config()

        # 记录清洗日志
        original_paths = request.get("model_paths", {})
        cleaned_paths = cleaned_model_paths
        removed_count = len(str(original_paths)) - len(str(cleaned_paths))
        if removed_count > 0:
            log_info("已清洗掉不在 Schema 中的模型路径字段")

        return {"success": True, "message": "模型路径设置已保存"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新模型路径设置失败: {str(e)}")


@router.put("/settings")
async def update_all_settings(request: Dict[str, Any]):
    """更新全部设置 - 经过 schema 清洗与校验"""
    try:
        cleaned_settings = schema_manager.clean_config(request)

        cfg = get_config()

        # musubi
        musubi_data = cleaned_settings.get("musubi", {})
        for k, v in musubi_data.items():
            if hasattr(cfg.musubi, k):
                setattr(cfg.musubi, k, v)

        # model_paths（动态更新）
        cleaned_model_paths = cleaned_settings.get("model_paths", {})
        if cleaned_model_paths and hasattr(cfg, 'model_paths'):
            for model_key, model_config in cleaned_model_paths.items():
                if isinstance(model_config, dict):
                    # 确保模型配置存在
                    if model_key not in cfg.model_paths._data:
                        cfg.model_paths._data[model_key] = {}
                    # 更新字段值（包括 _groups）
                    for field_key, field_value in model_config.items():
                        cfg.model_paths._data[model_key][field_key] = field_value

        # labeling
        lb = cleaned_settings.get("labeling", {})
        if "default_prompt" in lb:
            cfg.labeling.default_prompt = str(lb["default_prompt"]) or cfg.labeling.default_prompt
        if "translation_prompt" in lb:
            cfg.labeling.translation_prompt = str(lb["translation_prompt"]) or cfg.labeling.translation_prompt
        if "selected_model" in lb:
            cfg.labeling.selected_model = str(lb["selected_model"]).lower()
        if "delay_between_calls" in lb:
            try:
                cfg.labeling.delay_between_calls = float(lb["delay_between_calls"]) or 0.0
            except Exception:
                pass

        # 更新 models 配置（合并而不是替换，兼容旧版配置）
        models = lb.get("models", {})
        if models and isinstance(models, dict):
            # 确保 cfg.labeling.models 是字典类型
            if not isinstance(cfg.labeling.models, dict):
                cfg.labeling.models = {}
            
            # 获取 provider 的元数据，用于填充默认值
            from ...core.labeling.providers.registry import PROVIDER_METADATA
            
            # 合并配置：只更新传入的 provider，保留未传入的
            for provider_id, provider_config in models.items():
                if provider_config is not None:  # 允许空字典，但跳过 None
                    # 如果 provider_config 为空或缺少字段，自动填充默认值
                    metadata = PROVIDER_METADATA.get(provider_id)
                    if metadata and isinstance(provider_config, dict):
                        # 先用默认值初始化，然后只保留 metadata 中定义的字段
                        merged_config = {}
                        for field in metadata.config_fields:
                            # 优先使用用户配置的值，否则使用默认值
                            if field.key in provider_config:
                                merged_config[field.key] = provider_config[field.key]
                            elif field.default is not None:
                                merged_config[field.key] = field.default
                        
                        cfg.labeling.models[provider_id] = merged_config
                    else:
                        # 没有元数据或配置不是字典，直接保存
                        cfg.labeling.models[provider_id] = provider_config

        save_config(cfg)

        # 重新加载配置，刷新内存中的全局配置
        reload_config()

        # 刷新环境管理器中的workspace路径
        from ...core.environment import get_env_manager
        get_env_manager().refresh_from_config()

        return {"success": True, "message": "设置已保存"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新设置失败: {str(e)}")


class FixEnvironmentRequest(BaseModel):
    locale: Optional[str] = None  # 例如 "zh-CN", "en-US"


# ==================== 流式安装 API（保留）====================

class StartInstallationRequest(BaseModel):
    locale: Optional[str] = None


@router.post("/installation/start")
async def start_installation(request: StartInstallationRequest = StartInstallationRequest()):
    """
    启动安装任务（异步流式）

    返回 installation_id，前端通过 WebSocket 订阅实时进度
    """
    try:
        # 检查 workspace 是否已设置
        cfg = get_config()
        workspace_root = cfg.storage.workspace_root

        # 判断是否未设置（仍为默认相对路径）
        if not workspace_root or workspace_root.strip() in ('.', './workspace', 'workspace', ''):
            raise HTTPException(
                status_code=400,
                detail="工作区未设置，请先在「基础设置」中选择工作区目录"
            )

        from ...services.installation_service import get_installation_service

        use_china_mirror = request.locale and request.locale.startswith('zh')
        installation_service = get_installation_service()
        installation_id = await installation_service.start_installation(use_china_mirror=use_china_mirror)

        return {
            "success": True,
            "message": "安装任务已启动",
            "data": {
                "installation_id": installation_id
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动安装失败: {str(e)}")


@router.post("/installation/{installation_id}/cancel")
async def cancel_installation(installation_id: str):
    """取消安装任务"""
    try:
        from ...services.installation_service import get_installation_service

        installation_service = get_installation_service()
        success, message = await installation_service.cancel_installation(installation_id)

        return {
            "success": success,
            "message": message
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"取消安装失败: {str(e)}")


@router.get("/installation/{installation_id}/status")
async def get_installation_status(installation_id: str):
    """获取安装任务状态"""
    try:
        from ...services.installation_service import get_installation_service

        installation_service = get_installation_service()
        installation = installation_service.get_installation(installation_id)

        if not installation:
            raise HTTPException(status_code=404, detail="安装任务不存在")

        return {
            "success": True,
            "data": {
                "installation_id": installation.id,
                "state": installation.state.value,
                "created_at": installation.created_at.isoformat() if installation.created_at else None,
                "started_at": installation.started_at.isoformat() if installation.started_at else None,
                "completed_at": installation.completed_at.isoformat() if installation.completed_at else None,
                "error_message": installation.error_message
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取安装状态失败: {str(e)}")
