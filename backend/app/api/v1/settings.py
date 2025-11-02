"""
设置 API 路由：配置读取、保存与环境修复
"""

from fastapi import APIRouter, HTTPException, Response
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel
from typing import Dict, Any, Optional
from dataclasses import asdict
from pathlib import Path

from ...core.config import get_config, save_config, reload_config
from ...core.schema_manager import schema_manager
from ...utils.git_utils import check_submodule_status, get_musubi_releases, clear_musubi_cache
from ...services.musubi_fix_service import musubi_fix_service
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
        # 获取当前 musubi 版本信息（在线程池中执行，避免阻塞事件循环）
        version_info = await run_in_threadpool(check_submodule_status)

        # 序列化配置
        config_data = serialize_config()

        # 更新 musubi 版本信息
        config_data["musubi"]["version"] = version_info.get("version", "")
        config_data["musubi"]["status"] = version_info.get("status", "unknown")

        return {"success": True, "message": "配置获取成功", "data": config_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"配置获取失败: {str(e)}")


@router.post("/settings/musubi/check-status")
async def check_musubi_status():
    try:
        # 获取项目根目录（从环境管理器）
        from ...core.environment import get_paths

        paths = get_paths()
        project_root = str(paths.project_root)

        # 在线程池中执行，避免阻塞事件循环
        status_info = await run_in_threadpool(check_submodule_status, project_root)

        # 回写最新状态
        cfg = get_config()
        cfg.musubi.status = status_info.get("status", "error")
        cfg.musubi.version = status_info.get("version", "")
        cfg.musubi.last_check = status_info.get("commit_date", "")
        save_config(cfg)

        return {
            "success": True,
            "message": "状态已更新",
            "data": {
                "status": status_info.get("status", "error"),
                "version": status_info.get("version", ""),
                "commit_hash": status_info.get("commit_hash", ""),
                "commit_date": status_info.get("commit_date", ""),
                "branch": status_info.get("branch", ""),
                "message": status_info.get("message", "")
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"状态检查失败: {str(e)}")


@router.get("/settings/musubi/releases")
async def get_musubi_releases_api(limit: int = 10, force_refresh: bool = False):
    """获取 musubi 发布历史"""
    try:
        # 获取项目根目录（从环境管理器）
        from ...core.environment import get_paths

        paths = get_paths()
        project_root = str(paths.project_root)

        # 在线程池中执行，避免阻塞事件循环
        releases = await run_in_threadpool(get_musubi_releases, project_root, min(limit, 20), force_refresh)

        return {
            "success": True,
            "message": "发布历史获取成功" + (" (已刷新)" if force_refresh else " (使用缓存)"),
            "data": releases
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取发布历史失败: {str(e)}")


@router.delete("/settings/musubi/releases/cache", status_code=204)
async def clear_musubi_releases_cache():
    """清除 musubi 发布历史缓存（返回 204）"""
    try:
        # 获取项目根目录（从环境管理器）
        from ...core.environment import get_paths

        paths = get_paths()
        project_root = str(paths.project_root)

        # 在线程池中执行，避免阻塞事件循环
        await run_in_threadpool(clear_musubi_cache, project_root)
        return Response(status_code=204)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"缓存清除失败: {str(e)}")


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


@router.post("/settings/musubi/fix-environment")
async def fix_musubi_environment(request: FixEnvironmentRequest = FixEnvironmentRequest()):
    """修复训练环境（调用 setup_portable_uv.ps1）- 旧版阻塞式"""
    try:
        use_china_mirror = request.locale and request.locale.startswith('zh')
        success, message = await musubi_fix_service.fix_environment(use_china_mirror=use_china_mirror)
        return {
            "success": success,
            "message": message
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"修复训练环境失败: {str(e)}")


# ==================== 新的流式安装 API ====================

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


@router.post("/settings/musubi/fix-installation")
async def fix_musubi_installation():
    """修复训练安装（musubi-tuner 子模块）"""
    try:
        success, message = await musubi_fix_service.fix_trainer_installation()
        return {
            "success": success,
            "message": message
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"修复训练安装失败: {str(e)}")


@router.post("/settings/musubi/switch-version")
async def switch_musubi_version(request: Dict[str, Any]):
    """切换 musubi-tuner 到指定版本"""
    try:
        version = request.get("version")
        commit_hash = request.get("commit_hash")

        if not version or not commit_hash:
            raise HTTPException(status_code=400, detail="缺少版本号或commit hash")

        # 获取项目路径
        from ...core.environment import get_paths
        paths = get_paths()
        musubi_dir = paths.musubi_dir

        if not musubi_dir.exists():
            raise HTTPException(status_code=404, detail="musubi-tuner 目录不存在")

        # 执行 git checkout
        import subprocess
        log_info(f"切换 musubi-tuner 到版本: {version} ({commit_hash})")

        # 1. 先 fetch 确保有最新的 tags
        # 在线程池中执行外部进程，避免阻塞事件循环
        fetch_result = await run_in_threadpool(
            subprocess.run,
            ["git", "fetch", "--tags"],
            cwd=str(musubi_dir),
            capture_output=True,
            text=True,
            timeout=30
        )

        if fetch_result.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"获取远程标签失败: {fetch_result.stderr}"
            )

        # 2. 切换到指定 commit
        checkout_result = await run_in_threadpool(
            subprocess.run,
            ["git", "checkout", commit_hash],
            cwd=str(musubi_dir),
            capture_output=True,
            text=True,
            timeout=30
        )

        if checkout_result.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"切换版本失败: {checkout_result.stderr}"
            )

        log_success(f"成功切换到版本: {version}")

        # 更新配置中的版本信息
        cfg = get_config()
        cfg.musubi.version = version
        save_config(cfg)

        return {
            "success": True,
            "message": f"成功切换到版本 {version}"
        }

    except HTTPException:
        raise
    except Exception as e:
        log_error(f"切换版本失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"切换版本失败: {str(e)}")


@router.get("/settings/musubi/environment-status")
async def get_musubi_environment_status():
    """获取训练环境状态"""
    try:
        status = await musubi_fix_service.check_environment_status()
        return {
            "success": True,
            "message": "环境状态检查完成",
            "data": status
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"检查环境状态失败: {str(e)}")
