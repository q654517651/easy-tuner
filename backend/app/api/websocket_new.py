"""
新的统一WebSocket路由 - 简化设计
"""

import os
import asyncio
import json
import logging
import uuid
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Optional

from ..core.websocket.manager import get_websocket_manager
from ..core.state.manager import get_state_manager
from ..services.gpu_monitor import gpu_monitor

logger = logging.getLogger(__name__)

websocket_router = APIRouter()
DEBUG_WS = os.getenv('EASYTUNER_DEBUG_WS', '0') not in ('0', 'false', 'False', None)

# -------- 系统级 GPU 指标 WS（全局单采样器，多订阅者） --------
_gpu_clients: dict[str, WebSocket] = {}
_gpu_sampler_task: asyncio.Task | None = None
_gpu_interval_sec: float = 1.5

async def _gpu_sampler_loop():
    global _gpu_clients, _gpu_sampler_task
    if DEBUG_WS:
        logger.info("[WS][gpu] sampler loop started")
    try:
        while True:
            if not _gpu_clients:
                if DEBUG_WS:
                    logger.info("[WS][gpu] no subscribers, sampler loop exit")
                return
            try:
                gpus = gpu_monitor.get_gpu_info() or gpu_monitor.get_mock_data()
            except Exception as e:
                logger.error(f"[WS][gpu] sample failed: {e}")
                gpus = gpu_monitor.get_mock_data()

            payload = {
                'gpus': [
                    {
                        'id': g.id,
                        'name': g.name,
                        'memory_total': g.memory_total,
                        'memory_used': g.memory_used,
                        'memory_free': g.memory_free,
                        'gpu_utilization': g.gpu_utilization,
                        'mem_utilization': getattr(g, 'mem_utilization', 0.0),
                        'temperature': g.temperature,
                        'power_draw': g.power_draw,
                        'power_limit': g.power_limit,
                        'fan_speed': g.fan_speed,
                    } for g in gpus
                ],
                'total_gpus': len(gpus),
                'ts': asyncio.get_event_loop().time(),
            }
            message = {
                'version': 1,
                'type': 'gpu_metrics',
                'task_id': 'system',
                'epoch': 0,
                'sequence': 0,
                'timestamp': asyncio.get_event_loop().time(),
                'payload': payload,
            }

            bad: list[str] = []
            for cid, ws in list(_gpu_clients.items()):
                try:
                    await ws.send_text(json.dumps(message, ensure_ascii=False))
                except Exception as e:
                    logger.debug(f"[WS][gpu] send failed {cid}: {e}")
                    bad.append(cid)
            for cid in bad:
                _gpu_clients.pop(cid, None)
            await asyncio.sleep(_gpu_interval_sec)
    finally:
        _gpu_sampler_task = None
        if DEBUG_WS:
            logger.info("[WS][gpu] sampler loop stopped")

@websocket_router.websocket("/system/gpu")
async def system_gpu_websocket(websocket: WebSocket):
    """系统级 GPU 指标 WebSocket：每 1.5s 推送一次 gpu_metrics 消息"""
    await websocket.accept()
    client_id = f"sysgpu_{uuid.uuid4().hex[:8]}"
    if DEBUG_WS:
        logger.info(f"[WS][gpu] accepted: {client_id}")
    try:
        _gpu_clients[client_id] = websocket
        global _gpu_sampler_task
        if _gpu_sampler_task is None or _gpu_sampler_task.done():
            _gpu_sampler_task = asyncio.create_task(_gpu_sampler_loop())

        # 维持连接：目前仅接收以检测断开
        while True:
            try:
                await websocket.receive_text()
            except WebSocketDisconnect:
                break
    except Exception as e:
        logger.error(f"[WS][gpu] exception {client_id}: {e}")
    finally:
        _gpu_clients.pop(client_id, None)
        if DEBUG_WS:
            logger.info(f"[WS][gpu] disconnected: {client_id}, remain={len(_gpu_clients)}")


@websocket_router.websocket("/training/{task_id}")
async def unified_training_websocket(websocket: WebSocket, task_id: str):
    """统一的训练WebSocket端点 - 替代多个分散的端点"""
    await _handle_training_websocket(websocket, task_id)

@websocket_router.websocket("/training/{task_id}/{tab}")
async def training_websocket_with_tab(websocket: WebSocket, task_id: str, tab: str):
    """兼容旧版本的训练WebSocket端点 - 支持tab参数"""
    await _handle_training_websocket(websocket, task_id)

async def _handle_training_websocket(websocket: WebSocket, task_id: str):
    """统一的训练WebSocket处理逻辑"""
    client_id = f"client_{task_id}_{uuid.uuid4().hex[:8]}"
    websocket_manager = get_websocket_manager()
    state_manager = get_state_manager()
    ctx = {'last': 'connected'}

    try:
        # 接受WebSocket连接
        await websocket.accept()
        logger.info(f"WebSocket连接建立: {client_id} -> {task_id}")
        if DEBUG_WS:
            logger.info(f"[WS][{client_id}] accepted for task {task_id}")

        # 添加到连接管理器
        await websocket_manager.add_connection(client_id, websocket, task_id)

        # 发送当前状态快照
        await websocket_manager.send_current_state(client_id, task_id)

        # 发送订阅确认
        confirmation = {
            'version': 1,
            'type': 'connected',
            'task_id': task_id,
            'epoch': 0,
            'sequence': 0,
            'timestamp': asyncio.get_event_loop().time(),
            'payload': {
                'client_id': client_id,
                'subscribed_to': task_id,
                'message': '连接建立成功'
            }
        }
        await websocket.send_text(json.dumps(confirmation, ensure_ascii=False))

        # 保持连接并处理客户端消息
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                try:
                    msg_type = message.get('type', '')
                    ctx['last'] = f"message:{msg_type}"
                except Exception:
                    pass
                await handle_client_message(client_id, task_id, message, websocket, ctx)

            except json.JSONDecodeError:
                error_response = {
                    'version': 1,
                    'type': 'error',
                    'task_id': task_id,
                    'epoch': 0,
                    'sequence': 0,
                    'timestamp': asyncio.get_event_loop().time(),
                    'payload': {'error': '无效的JSON格式'}
                }
                await websocket.send_text(json.dumps(error_response))

    except WebSocketDisconnect:
        logger.info(f"WebSocket正常断开: {client_id}")
        if DEBUG_WS:
            logger.info(f"[WS][{client_id}] disconnect, last={ctx.get('last')}")
    except Exception as e:
        logger.error(f"WebSocket异常: {client_id}: {e}", exc_info=True)
    finally:
        # 清理连接
        await websocket_manager.remove_connection(client_id)
        if DEBUG_WS:
            logger.info(f"[WS][{client_id}] removed from manager")


async def handle_client_message(client_id: str, task_id: str, message: dict, websocket: WebSocket, ctx: dict | None = None):
    """处理客户端消息"""
    msg_type = message.get("type", "")

    if msg_type == "ping":
        # 心跳响应
        pong_response = {
            'version': 1,
            'type': 'pong',
            'task_id': task_id,
            'epoch': 0,
            'sequence': 0,
            'timestamp': asyncio.get_event_loop().time(),
            'payload': {
                'original_timestamp': message.get('timestamp'),
                'server_time': asyncio.get_event_loop().time()
            }
        }
        await websocket.send_text(json.dumps(pong_response))

    elif msg_type == "request_state":
        # 请求当前状态
        websocket_manager = get_websocket_manager()
        await websocket_manager.send_current_state(client_id, task_id)

    elif msg_type == "request_history":
        # 请求历史数据
        if ctx is not None:
            ctx['last'] = 'request_history'
        await send_historical_data(client_id, task_id, message, websocket)

    else:
        # 未知消息类型
        error_response = {
            'version': 1,
            'type': 'error',
            'task_id': task_id,
            'epoch': 0,
            'sequence': 0,
            'timestamp': asyncio.get_event_loop().time(),
            'payload': {'error': f'未知消息类型: {msg_type}'}
        }
        await websocket.send_text(json.dumps(error_response))


async def send_historical_data(client_id: str, task_id: str, request: dict, websocket: WebSocket):
    """发送历史数据"""
    data_type = request.get('data_type', 'logs')

    try:
        if DEBUG_WS:
            logger.info(f"[WS][{client_id}] send_historical_data type={data_type}")
        if data_type == 'logs':
            await send_historical_logs(client_id, task_id, request, websocket)
        elif data_type == 'metrics':
            await send_historical_metrics(client_id, task_id, request, websocket)
        elif data_type == 'transitions':
            await send_transition_history(client_id, task_id, websocket)
        else:
            raise ValueError(f"不支持的数据类型: {data_type}")

    except Exception as e:
        logger.error(f"发送历史数据失败 {client_id}: {e}")
        error_response = {
            'version': 1,
            'type': 'error',
            'task_id': task_id,
            'epoch': 0,
            'sequence': 0,
            'timestamp': asyncio.get_event_loop().time(),
            'payload': {'error': f'获取历史数据失败: {str(e)}'}
        }
        await websocket.send_text(json.dumps(error_response))


async def send_historical_logs(client_id: str, task_id: str, request: dict, websocket: WebSocket):
    """发送历史日志"""
    since_offset = request.get('since_offset', request.get('sinceOffset', 0))

    try:
        # 优先从文件读取（运行中也能获取到最新行）
        from pathlib import Path
        from ..core.config import get_config

        cfg = get_config()
        log_file = Path(cfg.storage.workspace_root) / 'tasks' / task_id / 'train.log'

        logs_all = []
        total = 0
        if log_file.exists():
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    logs_all = [ln.rstrip('\n\r') for ln in f.readlines() if ln.strip()]
            except UnicodeDecodeError:
                try:
                    with open(log_file, 'r', encoding='gbk') as f:
                        logs_all = [ln.rstrip('\n\r') for ln in f.readlines() if ln.strip()]
                except Exception:
                    logs_all = []
        total = len(logs_all)

        start = min(max(int(since_offset or 0), 0), total)
        logs_to_send = logs_all[start:]
        new_offset = start + len(logs_to_send)

        response = {
            'version': 1,
            'type': 'historical_logs',
            'task_id': task_id,
            'epoch': 0,
            'sequence': 0,
            'timestamp': asyncio.get_event_loop().time(),
            'payload': {
                'logs': logs_to_send,
                'since_offset': since_offset,
                'new_offset': new_offset,
                'total_logs': total
            }
        }

        # 若文件没有，回退到内存（兼容非运行态的历史）
        if total == 0:
            from ..core.training.manager_new import get_training_manager
            training_manager = get_training_manager()
            task = training_manager.get_task(task_id)
            if task and hasattr(task, 'logs') and task.logs:
                start = min(max(int(since_offset or 0), 0), len(task.logs))
                logs_to_send = task.logs[start:]
                response['payload'].update({
                    'logs': logs_to_send,
                    'since_offset': since_offset,
                    'new_offset': start + len(logs_to_send),
                    'total_logs': len(task.logs)
                })

        if DEBUG_WS:
            logger.info(f"[WS][{client_id}] historical logs: since={since_offset}, total={response['payload']['total_logs']}, send={len(response['payload']['logs'])}, new={response['payload']['new_offset']}")
        await websocket.send_text(json.dumps(response, ensure_ascii=False))

    except Exception as e:
        raise e


async def send_historical_metrics(client_id: str, task_id: str, request: dict, websocket: WebSocket):
    """发送历史指标"""
    try:
        from ..services.tb_event_service import get_tb_event_service
        tb_service = get_tb_event_service()
        metrics = tb_service.parse_scalars(task_id, keep=("loss", "learning_rate", "epoch"))

        response = {
            'version': 1,
            'type': 'historical_metrics',
            'task_id': task_id,
            'epoch': 0,
            'sequence': 0,
            'timestamp': asyncio.get_event_loop().time(),
            'payload': {
                'metrics': metrics,
                'total_metrics': len(metrics)
            }
        }

        await websocket.send_text(json.dumps(response, ensure_ascii=False))

    except Exception as e:
        raise e


async def send_transition_history(client_id: str, task_id: str, websocket: WebSocket):
    """发送状态转换历史"""
    try:
        state_manager = get_state_manager()
        transitions = await state_manager.get_transition_history(task_id)

        transition_data = [
            {
                'from_state': t.from_state.value,
                'to_state': t.to_state.value,
                'cause_id': t.cause_id,
                'epoch': t.epoch,
                'timestamp': t.timestamp.isoformat(),
                'metadata': t.metadata
            }
            for t in transitions
        ]

        response = {
            'version': 1,
            'type': 'transition_history',
            'task_id': task_id,
            'epoch': 0,
            'sequence': 0,
            'timestamp': asyncio.get_event_loop().time(),
            'payload': {
                'transitions': transition_data,
                'total_transitions': len(transition_data)
            }
        }

        await websocket.send_text(json.dumps(response, ensure_ascii=False))

    except Exception as e:
        raise e


# 健康检查和统计端点
@websocket_router.websocket("/health")
async def websocket_health_check(websocket: WebSocket):
    """WebSocket健康检查端点"""
    await websocket.accept()

    try:
        websocket_manager = get_websocket_manager()
        state_manager = get_state_manager()

        # 获取统计信息
        ws_stats = await websocket_manager.get_connection_stats()
        state_stats = await state_manager.get_statistics()

        health_info = {
            'version': 1,
            'type': 'health',
            'task_id': 'system',
            'epoch': 0,
            'sequence': 0,
            'timestamp': asyncio.get_event_loop().time(),
            'payload': {
                'status': 'healthy',
                'websocket_stats': ws_stats,
                'state_stats': state_stats
            }
        }

        await websocket.send_text(json.dumps(health_info))
        await websocket.close()

    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        await websocket.close(code=1011, reason="Health check failed")
