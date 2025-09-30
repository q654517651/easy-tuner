"""
AI Client - AI服务调用客户端 (FastAPI Backend version)
"""

import base64
import json
import requests
from typing import Optional, List, Dict, Any, Union
from enum import Enum

from ...utils.logger import log_error, log_info
from ...utils.exceptions import AIServiceError
from ..config import get_config

class ModelType(Enum):
    """AI模型类型"""
    GPT = "gpt"
    LM_STUDIO = "lm_studio" 
    LOCAL_QWEN_VL = "local_qwen_vl"

class AIClient:
    """AI服务客户端"""
    
    def __init__(self):
        self.config = get_config()
        self._setup_clients()
    
    def _setup_clients(self):
        """设置各种AI客户端"""
        # 从新配置结构加载设置
        labeling_config = self.config.labeling
        
        # GPT客户端设置
        self.gpt_config = {
            'api_key': labeling_config.models.gpt.api_key,
            'base_url': labeling_config.models.gpt.base_url,
            'model': labeling_config.models.gpt.model_name,
            'max_tokens': labeling_config.models.gpt.max_tokens,
            'temperature': labeling_config.models.gpt.temperature
        }
        
        # 已移除 Claude 客户端设置
        
        # LM Studio配置
        self.lm_studio_config = {
            'base_url': labeling_config.models.lm_studio.base_url,
            'model': labeling_config.models.lm_studio.model_name,
            'max_tokens': labeling_config.models.lm_studio.max_tokens,
            'temperature': labeling_config.models.lm_studio.temperature
        }
        
        # 本地Qwen-VL配置
        self.local_qwen_config = {
            'base_url': labeling_config.models.local_qwen_vl.base_url,
            'model': labeling_config.models.local_qwen_vl.model_name,
            'max_tokens': labeling_config.models.local_qwen_vl.max_tokens,
            'temperature': labeling_config.models.local_qwen_vl.temperature
        }
        
    
    def call_ai(self, 
                model_type: Union[str, ModelType],
                prompt: str,
                content: Optional[str] = None,
                image_path: Optional[str] = None,
                **kwargs) -> str:
        """调用AI服务"""
        try:
            # 转换模型类型
            if isinstance(model_type, str):
                # 支持各种格式转换
                model_key = model_type.lower().replace(' ', '_')
                if model_key in ['gpt', 'lm_studio', 'local_qwen_vl']:
                    model_type = ModelType(model_key)
                else:
                    # 向后兼容旧的格式
                    if model_key in ['lm_studio', 'local']:
                        model_type = ModelType.LM_STUDIO
                    elif model_key == 'gpt':
                        model_type = ModelType.GPT
                    else:
                        raise AIServiceError(model_type, f"不支持的模型类型: {model_type}")
            
            # 构建消息
            messages = self._build_messages(prompt, content, image_path)
            
            # 调用相应的服务
            if model_type == ModelType.GPT:
                return self._call_gpt(messages, **kwargs)
            elif model_type == ModelType.LM_STUDIO:
                return self._call_lm_studio(messages, **kwargs)
            elif model_type == ModelType.LOCAL_QWEN_VL:
                return self._call_local_qwen_vl(messages, **kwargs)
            else:
                raise AIServiceError(str(model_type), "不支持的模型类型")
                
        except Exception as e:
            error_msg = f"AI调用失败: {str(e)}"
            log_error(error_msg)
            raise AIServiceError(str(model_type), error_msg)
    
    def _build_messages(self, 
                       prompt: str, 
                       content: Optional[str] = None, 
                       image_path: Optional[str] = None) -> List[Dict[str, Any]]:
        """构建消息列表"""
        if image_path:
            # 多模态消息（文本+图像）
            try:
                base64_image = self._image_to_base64(image_path)
                return [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}},
                    ],
                }]
            except Exception as e:
                log_error(f"图像编码失败: {str(e)}")
                # 回退到纯文本模式
                return [{"role": "user", "content": f"{prompt}\n[图像加载失败]"}]
        
        # 纯文本消息
        messages = [{"role": "user", "content": prompt}]
        if content:
            messages.append({"role": "user", "content": content})
        
        return messages
    
    def _image_to_base64(self, file_path: str) -> str:
        """将图像转换为base64编码"""
        try:
            with open(file_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read())
                return encoded_string.decode("utf-8")
        except Exception as e:
            raise Exception(f"图像编码失败: {str(e)}")
    
    def _call_gpt(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        """调用GPT服务"""
        try:
            from openai import OpenAI

            # 检查是否启用
            if self.config.labeling.selected_model != 'gpt' and not self.config.labeling.models.gpt.enabled:
                raise AIServiceError("GPT", "GPT服务未启用")

            # 检查API Key
            if not self.gpt_config['api_key']:
                raise AIServiceError("GPT", "GPT API Key未设置")

            # 创建OpenAI客户端
            client = OpenAI(
                api_key=self.gpt_config['api_key'],
                base_url=self.gpt_config['base_url']
            )

            response = client.chat.completions.create(
                model=kwargs.get('model', self.gpt_config['model']),
                messages=messages,
                max_tokens=kwargs.get('max_tokens', self.gpt_config['max_tokens']),
                temperature=kwargs.get('temperature', self.gpt_config['temperature'])
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            raise AIServiceError("GPT", f"GPT调用失败: {str(e)}")
    
    def _call_lm_studio(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        """调用LM Studio本地服务"""
        try:
            # 检查是否启用
            if self.config.labeling.selected_model != 'lm_studio' and not self.config.labeling.models.lm_studio.enabled:
                raise AIServiceError("LM_Studio", "LM Studio服务未启用")
            
            url = f"{self.lm_studio_config['base_url']}/chat/completions"
            
            payload = {
                "model": kwargs.get('model', self.lm_studio_config['model']),
                "messages": messages,
                "max_tokens": kwargs.get('max_tokens', self.lm_studio_config['max_tokens']),
                "temperature": kwargs.get('temperature', self.lm_studio_config['temperature']),
                "stream": False
            }
            
            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            return result['choices'][0]['message']['content'].strip()
            
        except requests.RequestException as e:
            raise AIServiceError("LM_Studio", f"LM Studio连接失败: {str(e)}")
        except Exception as e:
            raise AIServiceError("LM_Studio", f"LM Studio调用失败: {str(e)}")


    def _call_local_qwen_vl(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        """调用本地 Qwen-VL 模型服务"""
        try:
            # 判断是否启用（选择的模型优先生效）
            if self.config.labeling.selected_model != 'local_qwen_vl' and not self.config.labeling.models.local_qwen_vl.enabled:
                raise AIServiceError("Local_Qwen_VL", "本地Qwen-VL服务未启用")

            url = f"{self.local_qwen_config['base_url']}/chat/completions"

            payload = {
                "model": kwargs.get('model', self.local_qwen_config['model']),
                "messages": messages,
                "max_tokens": kwargs.get('max_tokens', self.local_qwen_config['max_tokens']),
                "temperature": kwargs.get('temperature', self.local_qwen_config['temperature']),
                "stream": False
            }

            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()

            result = response.json()
            return result['choices'][0]['message']['content'].strip()

        except requests.RequestException as e:
            raise AIServiceError("Local_Qwen_VL", f"本地Qwen-VL连接失败: {str(e)}")
        except Exception as e:
            raise AIServiceError("Local_Qwen_VL", f"本地Qwen-VL调用失败: {str(e)}")