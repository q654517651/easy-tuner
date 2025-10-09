# backend/app/services/tb_event_service.py
from __future__ import annotations
from pathlib import Path
from typing import Dict, List, Any, Iterable, Optional
from ..utils.logger import log_info, log_error
from ..core.training.tensorboard.tfrecord_reader import find_event_file_for_task, TFRecordReader
from ..core.training.tensorboard.tensorboard_proto import get_proto_parser

ScalarPoint = Dict[str, float | int]

# Tag别名映射 - 支持多种命名方式
TAG_ALIASES: Dict[str, set[str]] = {
    "loss": {"loss", "train/loss", "Loss", "train_total_loss", "training_loss", "loss/current", "loss/average", "loss/epoch"},
    "learning_rate": {"learning_rate", "lr", "train/lr", "LearningRate", "train_lr", "lr/unet", "lr/group0"},
    "epoch": {"epoch", "Epoch", "train_epoch", "train/epoch", "step/epoch", "Epoch_Number"},
}


class TBEventService:
    """TensorBoard事件解析服务 - 不依赖tensorflow/tensorboard"""

    def __init__(self, workspace: Path = None):
        if workspace is None:
            workspace = Path("workspace")
        self.workspace = Path(workspace)

    def parse_scalars(self, task_id: str, keep: Iterable[str] = ("loss", "learning_rate", "epoch")) -> Dict[str, List[ScalarPoint]]:
        """解析训练任务的标量指标"""

        # 查找事件文件
        event_file = find_event_file_for_task(self.workspace, task_id)
        if not event_file:
            log_info(f"任务 {task_id} 未找到事件文件")
            return {}

        log_info(f"解析事件文件: {event_file}")

        try:
            # 准备结果存储
            raw_data: Dict[str, List[ScalarPoint]] = {}

            # 创建TFRecord读取器和protobuf解析器
            reader = TFRecordReader(event_file, verify_crc=False)
            parser = get_proto_parser()

            # 逐条读取并解析事件
            event_count = 0
            scalar_count = 0

            for payload in reader.read_records():
                event_count += 1
                event_data = parser.parse_event(payload)

                if not event_data or 'scalars' not in event_data:
                    continue

                # 处理事件中的标量数据
                wall_time = event_data['wall_time']
                step = event_data['step']

                for scalar in event_data['scalars']:
                    tag = scalar['tag']
                    value = scalar['value']
                    scalar_count += 1

                    # 存储原始数据
                    if tag not in raw_data:
                        raw_data[tag] = []

                    raw_data[tag].append({
                        "step": step,
                        "value": value,
                        "wall_time": wall_time
                    })

            log_info(f"解析完成: {event_count} 事件, {scalar_count} 标量, 找到tags: {list(raw_data.keys())}")

            # 按别名归一化并过滤结果
            result: Dict[str, List[ScalarPoint]] = {}

            # 如果keep为空，返回所有原始数据
            if not keep:
                return raw_data

            for metric_name in keep:
                # 获取该指标的所有可能别名
                aliases = TAG_ALIASES.get(metric_name, {metric_name})
                merged_data = []

                # 合并所有匹配的tag数据
                for tag, data_points in raw_data.items():
                    if tag.lower() in {alias.lower() for alias in aliases}:
                        merged_data.extend(data_points)

                if merged_data:
                    # 按step排序并去重
                    merged_data.sort(key=lambda x: x["step"])

                    # 简单去重：如果同一step有多个值，取最后一个
                    deduplicated = {}
                    for point in merged_data:
                        deduplicated[point["step"]] = point

                    result[metric_name] = list(deduplicated.values())

            log_info(f"归一化完成，输出指标: {list(result.keys())}")
            return result

        except Exception as e:
            log_error(f"解析TensorBoard文件失败: {e}", e)
            return {}

    def get_training_progress(self, task_id: str) -> Dict[str, Any]:
        """从TensorBoard日志获取训练进度信息"""
        try:
            # 先解析所有指标来查看可用的标签
            all_scalars = self.parse_scalars(task_id, keep=())  # 空keep表示获取所有
            log_info(f"TensorBoard所有可用标签 - task_id: {task_id}, 标签: {list(all_scalars.keys())}")

            # 解析关键指标
            scalars = self.parse_scalars(task_id, keep=("loss", "learning_rate", "epoch"))
            log_info(f"TensorBoard解析结果 - task_id: {task_id}, 找到的标量: {list(scalars.keys())}")

            # 初始化进度信息
            progress_info = {
                "current_epoch": 0,
                "total_epochs": 0,
                "current_step": 0,
                "total_steps": 0,
                "progress": 0.0,
                "loss": None,
                "learning_rate": None
            }

            # 从epoch数据获取进度
            if "epoch" in scalars and scalars["epoch"]:
                epoch_data = scalars["epoch"]
                if epoch_data:
                    # 获取最新的epoch信息
                    latest_epoch = epoch_data[-1]
                    current_epoch = int(latest_epoch["value"])
                    current_step = latest_epoch["step"]

                    progress_info["current_epoch"] = current_epoch
                    progress_info["current_step"] = current_step
            else:
                # 没有epoch数据，从loss数据推算step和epoch
                log_info(f"任务 {task_id} 没有epoch标签，尝试从loss数据推算进度")

            # 从loss数据获取最新loss值和额外的step信息
            if "loss" in scalars and scalars["loss"]:
                loss_data = scalars["loss"]
                if loss_data:
                    latest_loss = loss_data[-1]
                    progress_info["loss"] = latest_loss["value"]

                    # 更新step信息（loss通常记录更频繁）
                    if latest_loss["step"] > progress_info["current_step"]:
                        progress_info["current_step"] = latest_loss["step"]

            # 从learning_rate数据获取最新学习率
            if "learning_rate" in scalars and scalars["learning_rate"]:
                lr_data = scalars["learning_rate"]
                if lr_data:
                    latest_lr = lr_data[-1]
                    progress_info["learning_rate"] = latest_lr["value"]

            # 尝试推断总步数（如果有足够的数据）
            # 这里可以根据实际的训练器日志模式来优化
            if progress_info["current_step"] > 0 and progress_info["current_epoch"] > 0:
                # 粗略估算：当前步数 / 当前epoch = 每个epoch的步数
                steps_per_epoch = progress_info["current_step"] / max(progress_info["current_epoch"], 1)
                if steps_per_epoch > 0:
                    # 需要从配置中获取总epoch数，这里暂时用启发式方法
                    estimated_total_epochs = max(progress_info["current_epoch"] + 1, 10)  # 最少假设10个epoch
                    progress_info["total_steps"] = int(steps_per_epoch * estimated_total_epochs)
                    progress_info["total_epochs"] = estimated_total_epochs

            # 计算进度百分比
            if progress_info["total_steps"] > 0:
                progress_info["progress"] = min(1.0, progress_info["current_step"] / progress_info["total_steps"])
            elif progress_info["total_epochs"] > 0:
                progress_info["progress"] = min(1.0, progress_info["current_epoch"] / progress_info["total_epochs"])

            log_info(f"从TensorBoard获取进度: epoch {progress_info['current_epoch']}/{progress_info['total_epochs']}, "
                    f"step {progress_info['current_step']}/{progress_info['total_steps']}, "
                    f"progress {progress_info['progress']:.2%}")

            return progress_info

        except Exception as e:
            log_error(f"从TensorBoard获取训练进度失败: {e}", e)
            return {
                "current_epoch": 0,
                "total_epochs": 0,
                "current_step": 0,
                "total_steps": 0,
                "progress": 0.0,
                "loss": None,
                "learning_rate": None
            }


# 全局服务实例
_tb_event_service_instance: Optional[TBEventService] = None


def get_tb_event_service() -> TBEventService:
    """获取TensorBoard事件服务实例"""
    global _tb_event_service_instance
    if _tb_event_service_instance is None:
        _tb_event_service_instance = TBEventService()
    return _tb_event_service_instance
