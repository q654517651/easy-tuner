"""
GPU监控服务
支持通过NVML和nvidia-smi两种方式获取GPU信息
"""
import subprocess
import json
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from ..models.system import GPUMetrics

logger = logging.getLogger(__name__)


class GPUMonitorError(Exception):
    """GPU监控相关异常"""
    pass


class GPUMonitor:
    """GPU监控服务类"""

    def __init__(self):
        self.use_nvml = self._try_import_nvml()
        logger.info(f"GPU监控初始化完成，使用{'NVML' if self.use_nvml else 'nvidia-smi'}方式")

    def _try_import_nvml(self) -> bool:
        """尝试导入并初始化NVML"""
        try:
            import pynvml
            pynvml.nvmlInit()
            return True
        except ImportError:
            logger.warning("pynvml未安装，将使用nvidia-smi降级方案")
            return False
        except Exception as e:
            logger.warning(f"NVML初始化失败: {e}，将使用nvidia-smi降级方案")
            return False

    def get_gpu_count(self) -> int:
        """获取GPU数量"""
        if self.use_nvml:
            return self._get_gpu_count_nvml()
        else:
            return self._get_gpu_count_nvidia_smi()

    def get_gpu_info(self) -> List[GPUMetrics]:
        """获取所有GPU的详细信息"""
        if self.use_nvml:
            return self._get_info_nvml()
        else:
            return self._get_info_nvidia_smi()

    def get_gpu_info_by_id(self, gpu_id: int) -> Optional[GPUMetrics]:
        """获取指定GPU的信息"""
        try:
            all_gpus = self.get_gpu_info()
            for gpu in all_gpus:
                if gpu.id == gpu_id:
                    return gpu
            return None
        except Exception as e:
            logger.error(f"获取GPU {gpu_id}信息失败: {e}")
            return None

    def _get_gpu_count_nvml(self) -> int:
        """使用NVML获取GPU数量"""
        try:
            import pynvml
            return pynvml.nvmlDeviceGetCount()
        except Exception as e:
            logger.error(f"NVML获取GPU数量失败: {e}")
            return 0

    def _get_gpu_count_nvidia_smi(self) -> int:
        """使用nvidia-smi获取GPU数量"""
        try:
            result = subprocess.run([
                'nvidia-smi', '--query-gpu=count', '--format=csv,noheader,nounits'
            ], capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                return len(result.stdout.strip().split('\n'))
            else:
                logger.error(f"nvidia-smi命令失败: {result.stderr}")
                return 0
        except FileNotFoundError:
            logger.error("nvidia-smi命令不存在")
            return 0
        except Exception as e:
            logger.error(f"nvidia-smi获取GPU数量失败: {e}")
            return 0

    def _get_info_nvml(self) -> List[GPUMetrics]:
        """使用NVML获取GPU详细信息"""
        try:
            import pynvml

            gpus = []
            device_count = pynvml.nvmlDeviceGetCount()

            for i in range(device_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)

                # 基本信息
                name_raw = pynvml.nvmlDeviceGetName(handle)
                # 兼容不同版本的pynvml，有些版本返回bytes，有些返回str
                if isinstance(name_raw, bytes):
                    name = name_raw.decode('utf-8')
                else:
                    name = str(name_raw)

                # 显存信息
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                memory_total = mem_info.total // 1024 // 1024  # 转换为MB
                memory_used = mem_info.used // 1024 // 1024
                memory_free = mem_info.free // 1024 // 1024
                memory_utilization = (memory_used / memory_total) * 100

                # GPU利用率
                try:
                    util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                    gpu_utilization = util.gpu
                except:
                    gpu_utilization = 0.0

                # 温度
                try:
                    temperature = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                except:
                    temperature = 0

                # 功耗信息
                try:
                    power_draw = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0  # 转换为瓦特
                except:
                    power_draw = 0.0

                try:
                    power_limit = pynvml.nvmlDeviceGetPowerManagementLimitConstraints(handle)[1] / 1000.0
                except:
                    power_limit = 0.0

                # 风扇转速
                fan_speed = None
                try:
                    fan_speed = pynvml.nvmlDeviceGetFanSpeed(handle)
                except:
                    pass

                gpu_metrics = GPUMetrics(
                    id=i,
                    name=name,
                    memory_total=memory_total,
                    memory_used=memory_used,
                    memory_free=memory_free,
                    memory_utilization=round(memory_utilization, 1),
                    gpu_utilization=float(gpu_utilization),
                    temperature=temperature,
                    power_draw=round(power_draw, 1),
                    power_limit=round(power_limit, 1),
                    fan_speed=fan_speed
                )

                gpus.append(gpu_metrics)

            return gpus

        except Exception as e:
            logger.error(f"NVML获取GPU信息失败: {e}")
            raise GPUMonitorError(f"NVML获取GPU信息失败: {e}")

    def _get_info_nvidia_smi(self) -> List[GPUMetrics]:
        """使用nvidia-smi获取GPU详细信息"""
        try:
            # 使用nvidia-smi查询GPU信息
            cmd = [
                'nvidia-smi',
                '--query-gpu=index,name,memory.total,memory.used,memory.free,utilization.gpu,utilization.memory,temperature.gpu,power.draw,power.limit,fan.speed',
                '--format=csv,noheader,nounits'
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)

            if result.returncode != 0:
                logger.error(f"nvidia-smi命令失败: {result.stderr}")
                raise GPUMonitorError(f"nvidia-smi命令失败: {result.stderr}")

            gpus = []
            lines = result.stdout.strip().split('\n')

            for line in lines:
                if not line.strip():
                    continue

                parts = [part.strip() for part in line.split(',')]
                if len(parts) < 8:  # 至少需要8个字段
                    continue

                try:
                    gpu_id = int(parts[0])
                    name = parts[1]
                    memory_total = int(parts[2])
                    memory_used = int(parts[3])
                    memory_free = int(parts[4])
                    gpu_utilization = float(parts[5]) if parts[5] != '[Not Supported]' else 0.0
                    memory_utilization = float(parts[6]) if parts[6] != '[Not Supported]' else 0.0
                    temperature = int(parts[7]) if parts[7] != '[Not Supported]' else 0

                    # 功耗信息（可能不支持）
                    power_draw = 0.0
                    power_limit = 0.0
                    fan_speed = None

                    if len(parts) > 8 and parts[8] != '[Not Supported]':
                        power_draw = float(parts[8])
                    if len(parts) > 9 and parts[9] != '[Not Supported]':
                        power_limit = float(parts[9])
                    if len(parts) > 10 and parts[10] != '[Not Supported]':
                        fan_speed = int(parts[10])

                    gpu_metrics = GPUMetrics(
                        id=gpu_id,
                        name=name,
                        memory_total=memory_total,
                        memory_used=memory_used,
                        memory_free=memory_free,
                        memory_utilization=round(memory_utilization, 1),
                        gpu_utilization=round(gpu_utilization, 1),
                        temperature=temperature,
                        power_draw=round(power_draw, 1),
                        power_limit=round(power_limit, 1),
                        fan_speed=fan_speed
                    )

                    gpus.append(gpu_metrics)

                except (ValueError, IndexError) as e:
                    logger.warning(f"解析GPU信息行失败: {line}, 错误: {e}")
                    continue

            return gpus

        except FileNotFoundError:
            logger.error("nvidia-smi命令不存在")
            raise GPUMonitorError("nvidia-smi命令不存在，请安装NVIDIA驱动")
        except subprocess.TimeoutExpired:
            logger.error("nvidia-smi命令超时")
            raise GPUMonitorError("nvidia-smi命令执行超时")
        except Exception as e:
            logger.error(f"nvidia-smi获取GPU信息失败: {e}")
            raise GPUMonitorError(f"nvidia-smi获取GPU信息失败: {e}")

    def get_mock_data(self) -> List[GPUMetrics]:
        """返回模拟数据（用于开发环境）"""
        return [
            GPUMetrics(
                id=0,
                name="NVIDIA GeForce RTX 4090",
                memory_total=24576,
                memory_used=8192,
                memory_free=16384,
                memory_utilization=33.3,
                gpu_utilization=85.0,
                temperature=65,
                power_draw=350.5,
                power_limit=450.0,
                fan_speed=75
            ),
            GPUMetrics(
                id=1,
                name="NVIDIA GeForce RTX 4080",
                memory_total=16384,
                memory_used=4096,
                memory_free=12288,
                memory_utilization=25.0,
                gpu_utilization=45.0,
                temperature=58,
                power_draw=220.3,
                power_limit=320.0,
                fan_speed=60
            )
        ]


# 创建全局GPU监控实例
gpu_monitor = GPUMonitor()
