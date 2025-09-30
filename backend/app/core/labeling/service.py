"""
Labeling Service - 打标服务 (FastAPI Backend version)
"""

import time
import os
import threading
from typing import List, Dict, Optional, Callable, Tuple

from .ai_client import AIClient, ModelType
from ...utils.logger import log_info, log_error, log_success, log_progress
from ...utils.exceptions import LabelingError
from ..config import get_config

# 默认提示词
DEFAULT_LABELING_PROMPT = """
请为这张图片生成准确且详细的描述标签。
请使用简洁明了的语言，包含主要对象、场景、颜色、风格等关键信息。
请以英文单词和短语的形式输出，用逗号分隔。
"""

DEFAULT_TRANSLATION_PROMPT = """
请将以下英文描述翻译为中文，保持原意不变：
{content}
"""

class LabelingService:
    """AI打标服务"""
    
    def __init__(self):
        self.config = get_config()
        self.ai_client = AIClient()
        
    def label_images(self, 
                    images: List[str], 
                    labels: Dict[str, str], 
                    prompt: Optional[str] = None,
                    model_type: Optional[str] = None,
                    delay: float = 1.0,
                    progress_callback: Optional[Callable[[int, int, str], None]] = None) -> Tuple[int, str]:
        """批量打标图片"""
        try:
            if not images:
                return 0, "没有图片需要打标"
            
            # 使用配置中的默认提示词和模型
            if not prompt:
                prompt = self.config.labeling.default_prompt or DEFAULT_LABELING_PROMPT
            if not model_type:
                model_type = self.config.labeling.selected_model
            
            success_count = 0
            total_count = len(images)
            errors = []
            
            log_info(f"开始批量打标，共 {total_count} 张图片")
            
            for i, image_path in enumerate(images):
                try:
                    # 回调进度
                    if progress_callback:
                        progress_callback(i, total_count, f"正在处理: {image_path}")
                    
                    # 调用AI进行打标
                    result = self.ai_client.call_ai(
                        model_type=model_type,
                        prompt=prompt,
                        image_path=image_path
                    )
                    
                    if result and not result.startswith("AI调用失败"):
                        # 更新标签字典
                        filename = os.path.basename(image_path)
                        labels[image_path] = result
                        success_count += 1
                        
                        # 保存标签到txt文件
                        self._save_label_to_file(image_path, result)
                        
                        log_progress(f"打标成功 ({i+1}/{total_count}): {filename}")
                    else:
                        error_msg = f"打标失败: {result}"
                        errors.append(error_msg)
                        log_error(error_msg)
                    
                    # 延迟避免API限制
                    if i < total_count - 1 and delay > 0:
                        time.sleep(delay)
                        
                except Exception as e:
                    error_msg = f"处理图片失败 {image_path}: {str(e)}"
                    errors.append(error_msg)
                    log_error(error_msg)
            
            # 最终回调
            if progress_callback:
                progress_callback(total_count, total_count, "打标完成")
            
            # 生成结果消息
            message = f"成功打标 {success_count}/{total_count} 张图片"
            if errors:
                message += f"，失败 {len(errors)} 个"
                if len(errors) <= 3:
                    message += f": {'; '.join(errors)}"
            
            if success_count > 0:
                log_success(message)
            else:
                log_error(message)
            
            return success_count, message
            
        except Exception as e:
            error_msg = f"批量打标失败: {str(e)}"
            log_error(error_msg)
            raise LabelingError(error_msg)
    
    def label_single_image(self, 
                          image_path: str, 
                          prompt: Optional[str] = None,
                          model_type: Optional[str] = None) -> str:
        """打标单张图片"""
        try:
            if not prompt:
                prompt = self.config.labeling.default_prompt or DEFAULT_LABELING_PROMPT
            if not model_type:
                model_type = self.config.labeling.selected_model
            
            result = self.ai_client.call_ai(
                model_type=model_type,
                prompt=prompt,
                image_path=image_path
            )
            
            # 保存标签到txt文件
            if result and not result.startswith("AI调用失败"):
                self._save_label_to_file(image_path, result)
            
            return result
            
        except Exception as e:
            error_msg = f"单张图片打标失败 {image_path}: {str(e)}"
            log_error(error_msg)
            return f"错误: {error_msg}"
    
    def _save_label_to_file(self, image_path: str, label: str):
        """保存标签到txt文件"""
        try:
            txt_path = os.path.splitext(image_path)[0] + '.txt'
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(label)
        except Exception as e:
            log_error(f"保存标签文件失败 {image_path}: {str(e)}")
    
    def translate_labels(self, 
                        labels: Dict[str, str], 
                        prompt: Optional[str] = None,
                        model_type: str = "LM_STUDIO",
                        progress_callback: Optional[Callable[[int, int, str], None]] = None) -> Dict[str, Dict[str, str]]:
        """翻译标签"""
        try:
            if not labels:
                return {}
            
            if not prompt:
                prompt = self.config.labeling.translation_prompt or DEFAULT_TRANSLATION_PROMPT
            
            results = {}
            total_count = len(labels)
            success_count = 0
            
            log_info(f"开始批量翻译，共 {total_count} 个标签")
            
            for i, (image_path, original_label) in enumerate(labels.items()):
                try:
                    if progress_callback:
                        progress_callback(i, total_count, f"正在翻译: {image_path}")
                    
                    translated = self.ai_client.call_ai(
                        model_type=model_type,
                        prompt=prompt,
                        content=original_label
                    )
                    
                    if translated and not translated.startswith("AI调用失败"):
                        results[image_path] = {
                            'original': original_label,
                            'translated': translated
                        }
                        success_count += 1
                        log_progress(f"翻译成功 ({i+1}/{total_count})")
                    
                    # 短暂延迟
                    time.sleep(0.5)
                    
                except Exception as e:
                    log_error(f"翻译失败 {image_path}: {str(e)}")
            
            if progress_callback:
                progress_callback(total_count, total_count, "翻译完成")
            
            log_success(f"翻译完成，成功 {success_count}/{total_count} 个")
            return results
            
        except Exception as e:
            error_msg = f"批量翻译失败: {str(e)}"
            log_error(error_msg)
            raise LabelingError(error_msg)
    
    def get_default_prompt(self) -> str:
        """获取默认打标提示词"""
        return self.config.labeling.default_prompt or DEFAULT_LABELING_PROMPT
    
    def get_translation_prompt(self) -> str:
        """获取默认翻译提示词"""
        return self.config.labeling.translation_prompt or DEFAULT_TRANSLATION_PROMPT
    
    def test_ai_connection(self, model_type: str = "LM_STUDIO") -> bool:
        """测试AI服务连接"""
        return self.ai_client.test_connection(model_type)


# 创建全局单例实例
_labeling_service_instance = None
_lock = threading.Lock()


def get_labeling_service() -> LabelingService:
    """获取打标服务单例实例"""
    global _labeling_service_instance
    if _labeling_service_instance is None:
        with _lock:
            if _labeling_service_instance is None:
                _labeling_service_instance = LabelingService()
    return _labeling_service_instance