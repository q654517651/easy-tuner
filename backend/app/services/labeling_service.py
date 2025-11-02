"""
Labeling Service for FastAPI backend

This service provides all labeling-related operations for the EasyTuner application.
Uses the real LabelingService from the core module.
"""

import uuid
import asyncio
import threading
from typing import List, Dict, Any, Optional
from datetime import datetime

from ..models.labeling import (
    LabelingModelType, LabelingTaskStatus, BatchLabelingRequest,
    LabelingProgress, LabelingResult, AvailableModel
)
from ..core.labeling.providers.registry import get_provider, has_provider
from ..services.dataset_service import get_dataset_service
from ..core.exceptions import APIException, ValidationError
from ..core.config import get_config
from ..utils.logger import log_info, log_error, log_success
import os
import time


class LabelingServiceAPI:
    """打标服务API层 - 直接使用 Provider 架构"""

    def __init__(self):
        # 不再缓存配置对象，每次使用时动态获取最新配置
        self._dataset_service = get_dataset_service()
        self.tasks: Dict[str, LabelingProgress] = {}
        self.results: Dict[str, LabelingResult] = {}
        self._lock = threading.Lock()
        
        # ⚠️ 注意：此模型列表前端未使用，仅用于 /labeling/models API 兼容性
        # 前端实际使用 settings API 获取 Provider 元数据
        self.available_models = [
            AvailableModel(
                id="gpt-4-vision-preview",
                name="GPT-4 Vision Preview",
                type=LabelingModelType.GPT_4_VISION,
                description="OpenAI GPT-4 视觉模型，准确度高但速度较慢",
                supports_batch=True,
                max_batch_size=5,
                estimated_speed_per_image=3.0,
                is_available=False  # 初始化时设为 False，由 get_available_models() 动态更新
            ),
            AvailableModel(
                id="lm-studio-local",
                name="LM Studio (本地)",
                type=LabelingModelType.LM_STUDIO,
                description="本地部署的视觉语言模型",
                supports_batch=True,
                max_batch_size=10,
                estimated_speed_per_image=1.5,
                is_available=False  # 初始化时设为 False，由 get_available_models() 动态更新
            ),
            AvailableModel(
                id="qwen-vl-chat",
                name="通义千问 VL",
                type=LabelingModelType.QWEN_VL,
                description="本地Qwen-VL视觉语言模型",
                supports_batch=True,
                max_batch_size=8,
                estimated_speed_per_image=2.0,
                is_available=False  # 初始化时设为 False，由 get_available_models() 动态更新
            )
        ]
    
    async def _check_model_availability(self, provider_name: str) -> bool:
        """
        检查模型是否可用（使用 Provider 注册表）

        ⚠️ 注意：此方法目前前端未调用，仅用于后端 API 兼容性保留
        前端当前使用的是配置文件中的 selected_model，不依赖此检查
        """
        try:
            provider = get_provider(provider_name)
            if provider is None:
                return False
            return await provider.test_connection()
        except Exception:
            return False
    
    def _convert_model_type(self, api_model_type: LabelingModelType) -> str:
        """转换API模型类型到核心模型类型"""
        type_mapping = {
            LabelingModelType.GPT_4_VISION: "gpt",
            LabelingModelType.LM_STUDIO: "lm_studio",
            LabelingModelType.QWEN_VL: "local_qwen_vl"
        }
        return type_mapping.get(api_model_type, "lm_studio")
    
    async def get_available_models(self) -> List[AvailableModel]:
        """
        获取可用的打标模型

        ⚠️ 注意：此 API 前端未调用，仅保留用于后端兼容性
        前端实际使用 GET /api/v1/settings 获取 Provider 元数据
        """
        # 实时更新模型可用性（通过 Provider 注册表检查）
        for model in self.available_models:
            core_type = self._convert_model_type(model.type)
            model.is_available = await self._check_model_availability(core_type)

        return self.available_models
    
    async def start_batch_labeling(self, request: BatchLabelingRequest) -> str:
        """启动批量打标任务"""
        task_id = f"labeling_{uuid.uuid4().hex[:12]}"
        
        # 验证数据集
        dataset = self._dataset_service.get_dataset(request.dataset_id)
        if not dataset:
            raise ValidationError(f"数据集未找到: {request.dataset_id}")
        
        # 获取数据集图片
        images = self._dataset_service.get_dataset_images(request.dataset_id)
        
        # 过滤要处理的图片
        if request.image_ids:
            images = [img for img in images if img['filename'] in request.image_ids]
        
        if not images:
            raise ValidationError("没有找到要处理的图片")
        
        total_count = len(images)
        
        # 创建任务进度
        progress = LabelingProgress(
            task_id=task_id,
            status=LabelingTaskStatus.PENDING,
            total_count=total_count,
            completed_count=0,
            failed_count=0,
            progress_percentage=0.0,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        with self._lock:
            self.tasks[task_id] = progress
        
        # 异步启动处理任务
        asyncio.create_task(self._process_labeling_task(task_id, request, images))
        
        log_info(f"启动批量打标任务: {task_id}, 数据集: {request.dataset_id}, 图片数: {total_count}")
        
        return task_id
    
    async def get_labeling_progress(self, task_id: str) -> LabelingProgress:
        """获取打标进度"""
        if task_id not in self.tasks:
            raise ValidationError(f"任务未找到: {task_id}")
        
        return self.tasks[task_id]
    
    async def get_labeling_result(self, task_id: str) -> LabelingResult:
        """获取打标结果"""
        if task_id not in self.results:
            raise ValidationError(f"任务结果未找到: {task_id}")
        
        return self.results[task_id]
    
    async def cancel_labeling_task(self, task_id: str) -> bool:
        """取消打标任务"""
        if task_id not in self.tasks:
            raise ValidationError(f"任务未找到: {task_id}")
        
        task = self.tasks[task_id]
        if task.status in [LabelingTaskStatus.COMPLETED, LabelingTaskStatus.FAILED]:
            raise ValidationError("任务已完成，无法取消")
        
        with self._lock:
            task.status = LabelingTaskStatus.CANCELLED
            task.updated_at = datetime.now()
        
        log_info(f"取消打标任务: {task_id}")
        return True
    
    async def _process_labeling_task(self, task_id: str, request: BatchLabelingRequest, images: List[Dict[str, Any]]):
        """处理打标任务（异步处理）"""
        try:
            task = self.tasks[task_id]
            task.status = LabelingTaskStatus.RUNNING
            task.updated_at = datetime.now()
            
            start_time = datetime.now()
            results = []
            
            # 准备打标参数
            core_model_type = self._convert_model_type(request.model_type)
            prompt = request.prompt or get_config().labeling.default_prompt
            
            # 批量处理图片
            image_paths = []
            for img in images:
                if img['path']:
                    image_paths.append(img['path'])
            
            labels = {}
            
            def progress_callback(current: int, total: int, message: str):
                """进度回调函数"""
                nonlocal task
                if task.status == LabelingTaskStatus.CANCELLED:
                    return
                
                with self._lock:
                    task.completed_count = current
                    task.current_item = message
                    task.progress_percentage = (current / total * 100) if total > 0 else 0
                    task.updated_at = datetime.now()
                    
                    # 估算剩余时间
                    if current > 0:
                        elapsed = (datetime.now() - start_time).total_seconds()
                        avg_time_per_item = elapsed / current
                        remaining_items = total - current
                        task.estimated_remaining_seconds = int(avg_time_per_item * remaining_items)
            
            # 调用真实的打标服务
            try:
                # 若选择本地 Qwen‑VL，则走本地 Provider 执行一批
                # Provider only: sequential per-image via registry (no ai_client)
                key = (core_model_type or '').lower().strip().replace('-', '_').replace(' ', '_')
                provider = get_provider(key)
                if provider is None:
                    raise ValidationError(f"model not available: {core_model_type}")

                total_count = len(image_paths)
                delay_val = request.delay_between_requests or 1.0

                for i, img_path in enumerate(image_paths):
                    if task.status == LabelingTaskStatus.CANCELLED:
                        break
                    if progress_callback:
                        progress_callback(i, total_count, f"processing: {img_path}")

                    r = await provider.generate_label(img_path, prompt=prompt)

                    if r and getattr(r, 'ok', False) and getattr(r, 'text', None):
                        labels[img_path] = r.text or ''
                    else:
                        log_error(f"label failed: {img_path}")

                    if i < total_count - 1 and delay_val > 0:
                        time.sleep(delay_val)

                success_count = sum(1 for v in labels.values() if v)
                message = f"labeled {success_count}/{total_count} images"

                # legacy branch disabled to keep for reference
                if False and core_model_type == 'local_qwen_vl':
                    provider = QwenVLProvider()
                    weights_path = os.getenv('QWEN_VL_WEIGHTS')

                    def _run_provider_batch():
                        loop = asyncio.new_event_loop()
                        try:
                            asyncio.set_event_loop(loop)
                            return loop.run_until_complete(
                                provider.generate_labels(image_paths, prompt=prompt, weights_path=weights_path)
                            )
                        finally:
                            try:
                                loop.close()
                            except Exception:
                                pass

                    out: Dict[str, Any] = {}
                    t = threading.Thread(target=lambda: out.setdefault('res', _run_provider_batch()), daemon=True)
                    t.start(); t.join()
                    results_batch = out.get('res') or []

                    for i, (img_path, r) in enumerate(zip(image_paths, results_batch)):
                        if task.status == LabelingTaskStatus.CANCELLED:
                            break
                        if progress_callback:
                            progress_callback(i, total_count, f"处理: {img_path}")
                        if r and getattr(r, 'ok', False) and getattr(r, 'text', None):
                            caption = r.text or ""
                            labels[img_path] = caption
                            # 写入标签文件
                            try:
                                self._labeling_service._save_label_to_file(img_path, caption)
                            except Exception:
                                pass
                        else:
                            log_error(f"生成失败: {img_path}")

                    success_count = len(labels)
                    message = f"成功标注 {success_count}/{total_count} 张图片"
                elif False:
                    success_count, message = self._labeling_service.label_images(
                        images=image_paths,
                        labels=labels,
                        prompt=prompt,
                        model_type=core_model_type,
                        delay=request.delay_between_requests or 1.0,
                        progress_callback=progress_callback
                    )
                
                # 构建结果
                for i, img in enumerate(images):
                    image_path = img['path']
                    filename = img['filename']
                    
                    if image_path in labels:
                        # 成功打标
                        results.append({
                            "item_id": f"dataset_{request.dataset_id}_item_{filename}",
                            "filename": filename,
                            "success": True,
                            "caption": labels[image_path],
                            "confidence": 0.9  # 暂时固定置信度
                        })
                    else:
                        # 打标失败
                        task.failed_count += 1
                        results.append({
                            "item_id": f"dataset_{request.dataset_id}_item_{filename}",
                            "filename": filename,
                            "success": False,
                            "error": "打标失败"
                        })
                
                # 更新数据集中的标签
                if request.update_dataset and labels:
                    self._dataset_service.batch_update_labels(request.dataset_id, {
                        img['filename']: labels.get(img['path'], '') 
                        for img in images if img['path'] in labels
                    })
                
            except Exception as e:
                log_error(f"打标任务处理异常: {str(e)}")
                raise e
            
            # 完成任务
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()
            
            if task.status != LabelingTaskStatus.CANCELLED:
                with self._lock:
                    task.status = LabelingTaskStatus.COMPLETED
                    task.current_item = None
                    task.estimated_remaining_seconds = 0
                    task.updated_at = end_time
                    task.completed_count = success_count
                    task.failed_count = len(images) - success_count
                
                # 保存结果
                result = LabelingResult(
                    task_id=task_id,
                    dataset_id=request.dataset_id,
                    status=LabelingTaskStatus.COMPLETED,
                    total_processed=len(images),
                    successful_count=success_count,
                    failed_count=len(images) - success_count,
                    results=results,
                    execution_time_seconds=execution_time,
                    created_at=start_time,
                    completed_at=end_time
                )
                
                with self._lock:
                    self.results[task_id] = result
                
                log_success(f"打标任务完成: {task_id}, 成功: {success_count}/{len(images)}")
            
        except Exception as e:
            # 处理异常
            with self._lock:
                task.status = LabelingTaskStatus.FAILED
                task.error_message = str(e)
                task.updated_at = datetime.now()
            
            log_error(f"打标任务失败: {task_id}, 错误: {str(e)}")
    
    async def get_task_history(self, limit: int = 20) -> List[LabelingProgress]:
        """获取任务历史"""
        tasks = list(self.tasks.values())
        tasks.sort(key=lambda x: x.created_at, reverse=True)
        return tasks[:limit]

    async def label_single(self, dataset_id: str, filename: str, prompt: Optional[str] = None) -> Dict[str, Any]:
        """对单张图片进行打标并更新数据集标签"""
        # 获取图片路径
        image_path = self._dataset_service.get_image_path(dataset_id, filename)
        if not image_path:
            raise ValidationError(f"文件未找到: {filename}")

        # 使用核心打标服务（按当前选中模型 & 默认 prompt）
        selected_model = get_config().labeling.selected_model
        log_info(f"[LabelingService] 使用模型 '{selected_model}' 对 {filename} 进行打标")

        try:
            core_model_type = (selected_model or "").lower().strip().replace('-', '_').replace(' ', '_')
            from ..core.labeling.providers.registry import get_provider
            provider = get_provider(core_model_type)

            if provider is None:
                log_error(f"[LabelingService] Provider 不存在: {core_model_type}")
                raise ValidationError(f"打标模型不可用: {selected_model}，请检查设置页配置")

            # TODO: quick_config_check() 暂时禁用，未来用于测试服务连通性（不阻断调用）
            # 当前直接尝试调用，由 Provider 内部处理配置错误

            r = await provider.generate_label(image_path, prompt=prompt or None)

            # 检查打标结果
            if not r or not r.ok:
                # 打标失败，构建详细错误信息
                error_msg = "打标失败"
                if r:
                    if r.detail:
                        error_msg = f"{r.detail}"
                    elif r.error_code:
                        error_msg = f"打标失败 (错误码: {r.error_code})"
                log_error(f"[LabelingService] {error_msg} - 模型: {selected_model}, 文件: {filename}")
                return {"filename": filename, "success": False, "error": error_msg}

            caption = r.text or ""
            if not caption:
                log_error(f"[LabelingService] 返回结果为空 - 模型: {selected_model}, 文件: {filename}")
                return {"filename": filename, "success": False, "error": "打标失败：返回结果为空"}

            # 打标成功，写入数据集标签
            self._dataset_service.update_label(dataset_id, filename, caption)
            log_success(f"[LabelingService] 打标成功 - 模型: {selected_model}, 文件: {filename}, 标签长度: {len(caption)}")
            return {"filename": filename, "caption": caption, "success": True}

        except ValidationError as e:
            # ValidationError 直接向上抛出（前端能看到详细信息）
            raise e
        except Exception as e:
            log_error(f"[LabelingService] 打标异常 - 模型: {selected_model}, 文件: {filename}, 错误: {str(e)}")
            raise APIException(500, f"打标失败: {str(e)}")
    
    async def test_model_connection(self, model_id: str) -> Dict[str, Any]:
        """测试模型连接"""
        model = next((m for m in self.available_models if m.id == model_id), None)
        if not model:
            raise ValidationError(f"模型未找到: {model_id}")
        
        core_model_type = self._convert_model_type(model.type)

        try:
            # 使用 Provider 注册表测试连接
            provider = get_provider(core_model_type)
            if provider is None:
                return {
                    "model_id": model_id,
                    "is_connected": False,
                    "status": f"模型未注册: {core_model_type}",
                    "tested_at": datetime.now().isoformat()
                }

            is_connected = await provider.test_connection()
            return {
                "model_id": model_id,
                "is_connected": is_connected,
                "status": "连接成功" if is_connected else "连接失败",
                "tested_at": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "model_id": model_id,
                "is_connected": False,
                "status": f"连接失败: {str(e)}",
                "tested_at": datetime.now().isoformat()
            }


# Global service instance
_labeling_service_instance = None
_lock = threading.Lock()

def get_labeling_service_api() -> LabelingServiceAPI:
    """Get the global labeling service instance"""
    global _labeling_service_instance
    if _labeling_service_instance is None:
        with _lock:
            if _labeling_service_instance is None:
                _labeling_service_instance = LabelingServiceAPI()
    return _labeling_service_instance
