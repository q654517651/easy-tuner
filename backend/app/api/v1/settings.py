"""
设置 API 路由（与核心配置统一）
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from dataclasses import asdict
import os
from pathlib import Path

from ...core.config import get_config, save_config
from ...core.schema_manager import schema_manager
from ...utils.git_utils import check_submodule_status, get_musubi_releases, clear_musubi_cache
from ...services.musubi_fix_service import musubi_fix_service


router = APIRouter()


class AppSettings(BaseModel):
    musubi: Dict[str, Any]
    model_paths: Dict[str, Dict[str, Any]]
    labeling: Dict[str, Any]


def serialize_config() -> Dict[str, Any]:
    cfg = get_config()

    # 动态生成model_paths配置
    model_paths = {}
    valid_paths = schema_manager.get_valid_paths()

    for path in valid_paths:
        if path.startswith("model_paths."):
            parts = path.split('.')
            if len(parts) == 3:  # model_paths.qwen_image.dit_path
                model_key, field_key = parts[1], parts[2]
                if model_key not in model_paths:
                    model_paths[model_key] = {}

                # 获取实际值
                value = getattr(getattr(cfg.model_paths, model_key, object()), field_key, "")
                model_paths[model_key][field_key] = value

    return {
        "musubi": asdict(cfg.musubi),
        "model_paths": model_paths,
        "labeling": {
            "default_prompt": cfg.labeling.default_prompt,
            "translation_prompt": cfg.labeling.translation_prompt,
            "selected_model": cfg.labeling.selected_model,
            "delay_between_calls": cfg.labeling.delay_between_calls,
            "models": {
                "gpt": asdict(cfg.labeling.models.gpt),
                "lm_studio": asdict(cfg.labeling.models.lm_studio),
                "local_qwen_vl": asdict(cfg.labeling.models.local_qwen_vl),
            }
        }
    }


@router.get("/settings")
async def get_settings():
    try:
        return {"success": True, "message": "配置获取成功", "data": serialize_config()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"配置获取失败: {str(e)}")




@router.post("/settings/musubi/check-status")
async def check_musubi_status():
    try:
        # 获取项目根目录
        current_dir = Path(__file__).resolve()
        project_root = None

        # 向上查找项目根目录
        while current_dir.parent != current_dir:
            if (current_dir / "runtime" / "engines" / "musubi-tuner").exists():
                project_root = str(current_dir)
                break
            current_dir = current_dir.parent

        if project_root is None:
            # 如果没找到，尝试相对路径
            backend_dir = Path(__file__).resolve().parent.parent.parent.parent
            project_root = str(backend_dir.parent)

        status_info = check_submodule_status(project_root)

        # 更新配置中的状态信息
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
    """获取musubi发布历史"""
    try:
        # 获取项目根目录
        current_dir = Path(__file__).resolve()
        project_root = None

        # 向上查找项目根目录
        while current_dir.parent != current_dir:
            if (current_dir / "runtime" / "engines" / "musubi-tuner").exists():
                project_root = str(current_dir)
                break
            current_dir = current_dir.parent

        if project_root is None:
            # 如果没找到，尝试相对路径
            backend_dir = Path(__file__).resolve().parent.parent.parent.parent
            project_root = str(backend_dir.parent)

        releases = get_musubi_releases(project_root, min(limit, 20), force_refresh)  # 最多20个

        return {
            "success": True,
            "message": "发布历史获取成功" + (" (已刷新)" if force_refresh else " (使用缓存)"),
            "data": releases
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取发布历史失败: {str(e)}")


@router.delete("/settings/musubi/releases/cache")
async def clear_musubi_releases_cache():
    """清除musubi发布历史缓存"""
    try:
        # 获取项目根目录
        current_dir = Path(__file__).resolve()
        project_root = None

        # 向上查找项目根目录
        while current_dir.parent != current_dir:
            if (current_dir / "runtime" / "engines" / "musubi-tuner").exists():
                project_root = str(current_dir)
                break
            current_dir = current_dir.parent

        if project_root is None:
            # 如果没找到，尝试相对路径
            backend_dir = Path(__file__).resolve().parent.parent.parent.parent
            project_root = str(backend_dir.parent)

        success = clear_musubi_cache(project_root)

        return {
            "success": success,
            "message": "缓存清除成功" if success else "缓存清除失败或缓存不存在"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清除缓存失败: {str(e)}")


@router.get("/settings/model-paths/schema")
async def get_model_paths_schema():
    """获取模型路径schema（从缓存，毫秒级响应）"""
    try:
        schema = schema_manager.get_schema()
        return {"success": True, "data": schema}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取Schema失败: {str(e)}")


@router.put("/settings/model-paths")
async def update_model_paths_settings(request: Dict[str, Any]):
    """更新模型路径设置 - 基于schema验证和清理"""
    try:
        # 1. 验证和清理数据
        cleaned_settings = schema_manager.clean_config(request)

        # 2. 获取现有配置并更新
        cfg = get_config()

        # 3. 更新model_paths配置
        cleaned_model_paths = cleaned_settings.get("model_paths", {})
        if cleaned_model_paths:
            # 更新现有配置结构
            if hasattr(cfg, 'model_paths'):
                for model_key, model_config in cleaned_model_paths.items():
                    if hasattr(cfg.model_paths, model_key):
                        for field_key, field_value in model_config.items():
                            if hasattr(getattr(cfg.model_paths, model_key), field_key):
                                setattr(getattr(cfg.model_paths, model_key), field_key, field_value)

        # 4. 保存配置
        save_config(cfg)

        # 5. 记录清理日志
        original_paths = request.get("model_paths", {})
        cleaned_paths = cleaned_model_paths
        removed_count = len(str(original_paths)) - len(str(cleaned_paths))
        if removed_count > 0:
            print(f"清理了废弃的模型路径配置")

        return {"success": True, "message": "模型路径设置已保存"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存模型路径设置失败: {str(e)}")


@router.put("/settings")
async def update_all_settings(request: Dict[str, Any]):
    """更新所有设置 - 基于schema验证和清理"""
    try:
        # 1. 验证和清理数据
        cleaned_settings = schema_manager.clean_config(request)

        # 2. 获取现有配置
        cfg = get_config()

        # 3. 更新musubi配置
        musubi_data = cleaned_settings.get("musubi", {})
        for k, v in musubi_data.items():
            if hasattr(cfg.musubi, k):
                setattr(cfg.musubi, k, v)

        # 4. 更新model_paths配置（使用清理后的数据）
        cleaned_model_paths = cleaned_settings.get("model_paths", {})
        if cleaned_model_paths and hasattr(cfg, 'model_paths'):
            for model_key, model_config in cleaned_model_paths.items():
                if hasattr(cfg.model_paths, model_key):
                    for field_key, field_value in model_config.items():
                        if hasattr(getattr(cfg.model_paths, model_key), field_key):
                            setattr(getattr(cfg.model_paths, model_key), field_key, field_value)

        # 5. 更新labeling配置
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

        models = lb.get("models", {})
        for key in ("gpt", "lm_studio", "local_qwen_vl"):
            if key in models:
                m = models[key]
                target = getattr(cfg.labeling.models, key)
                for mk in ("api_key", "base_url", "model_name", "supports_video", "max_tokens", "temperature", "enabled"):
                    if mk in m and hasattr(target, mk):
                        setattr(target, mk, m[mk])

        # 6. 保存配置
        save_config(cfg)

        return {"success": True, "message": "设置已保存"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存设置失败: {str(e)}")


class FixEnvironmentRequest(BaseModel):
    locale: Optional[str] = None  # 语言配置，如 "zh-CN", "en-US"


@router.post("/settings/musubi/fix-environment")
async def fix_musubi_environment(request: FixEnvironmentRequest = FixEnvironmentRequest()):
    """修复训练环境 - 重新运行setup_portable_uv.ps1"""
    try:
        # 根据语言配置决定是否使用国内源
        use_china_mirror = request.locale and request.locale.startswith('zh')

        success, message = await musubi_fix_service.fix_environment(use_china_mirror=use_china_mirror)
        return {
            "success": success,
            "message": message
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"修复训练环境失败: {str(e)}")


@router.post("/settings/musubi/fix-installation")
async def fix_musubi_installation():
    """修复训练器安装 - 更新musubi-tuner子模块"""
    try:
        success, message = await musubi_fix_service.fix_trainer_installation()
        return {
            "success": success,
            "message": message
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"修复训练器安装失败: {str(e)}")


@router.get("/settings/musubi/environment-status")
async def get_musubi_environment_status():
    """检查训练环境状态"""
    try:
        status = await musubi_fix_service.check_environment_status()
        return {
            "success": True,
            "message": "环境状态检查完成",
            "data": status
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"检查环境状态失败: {str(e)}")

