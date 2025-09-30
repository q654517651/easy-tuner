"""
网络重试工具 - 支持HuggingFace镜像站自动切换
用于处理训练和缓存过程中的网络连接问题
"""

import os
import time
import subprocess
import ssl
from typing import Dict, List, Optional, Callable, Any
from pathlib import Path
from ..utils.logger import log_info, log_error, log_success


class NetworkRetryHelper:
    """网络重试助手 - 支持HuggingFace镜像站切换"""

    HF_MIRRORS = [
        "https://huggingface.co",  # 官方站点
        "https://hf-mirror.com",   # 镜像站
    ]

    def __init__(self, max_retries: int = 2, retry_delay: int = 3):
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def _is_network_error(self, error_text: str) -> bool:
        """检查是否为网络相关错误"""
        # 更精确的网络错误检测 - 避免误报
        specific_network_errors = [
            "SSLError", "SSL certificate", "certificate verify failed",
            "ConnectionError", "Connection timeout", "connection failed",
            "URLError", "Failed to connect", "Unable to connect",
            "Read timed out", "Connection refused", "Connection reset",
            "Name or service not known", "Temporary failure in name resolution",
            "Max retries exceeded", "Connection broken",
            "TLS handshake timeout", "SSL handshake failed",
            "requests.exceptions", "urllib3.exceptions",
            "HTTPSConnectionPool", "NewConnectionError"
        ]

        # 排除正常的训练日志
        if any(normal_log in error_text for normal_log in [
            "INFO:", "DEBUG:", "WARNING:",
            "set VAE model", "import network module",
            "steps:", "dtype:", "device:",
            "musubi_tuner", "torch.bfloat16"
        ]):
            return False

        # 检查是否包含具体的网络错误
        return any(keyword in error_text for keyword in specific_network_errors)

    def _set_hf_mirror(self, mirror_url: str):
        """设置HuggingFace镜像站环境变量"""
        if mirror_url == "https://hf-mirror.com":
            os.environ['HF_ENDPOINT'] = mirror_url
            log_info(f"切换到HF镜像站: {mirror_url}")
        elif "HF_ENDPOINT" in os.environ:
            # 恢复默认
            del os.environ['HF_ENDPOINT']
            log_info("恢复HF官方站点")

    def run_with_retry(self,
                      command: List[str],
                      cwd: str,
                      env: Dict[str, str],
                      log_callback: Optional[Callable[[str], None]] = None,
                      timeout: int = 1800,
                      log_file_path: Optional[str] = None) -> bool:
        """
        执行命令并在网络错误时自动重试和切换镜像站

        Args:
            command: 要执行的命令
            cwd: 工作目录
            env: 环境变量
            log_callback: 日志回调函数
            timeout: 超时时间(秒)

        Returns:
            bool: 是否执行成功
        """
        last_error = None

        for attempt in range(self.max_retries + 1):
            # 设置镜像站
            if attempt < len(self.HF_MIRRORS):
                self._set_hf_mirror(self.HF_MIRRORS[attempt])

            # 记录尝试信息
            mirror_info = f"(尝试 {attempt + 1}/{self.max_retries + 1}"
            if attempt < len(self.HF_MIRRORS):
                mirror_info += f", 镜像: {self.HF_MIRRORS[attempt]}"
            mirror_info += ")"

            log_info(f"执行命令 {mirror_info}: {' '.join(command[:3])}...")
            if log_callback:
                log_callback(f"执行命令 {mirror_info}: {' '.join(command[:3])}...")

            try:
                # 复制环境变量并应用当前镜像设置
                current_env = env.copy()
                if 'HF_ENDPOINT' in os.environ:
                    current_env['HF_ENDPOINT'] = os.environ['HF_ENDPOINT']

                proc = subprocess.Popen(
                    command,
                    cwd=cwd,
                    env=current_env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    bufsize=1
                )

                start_time = time.time()
                output_lines = []

                # 可选：打开日志文件（追加写），确保父目录存在
                log_file = None
                try:
                    if log_file_path:
                        p = Path(log_file_path)
                        p.parent.mkdir(parents=True, exist_ok=True)
                        log_file = p.open('a', encoding='utf-8')
                except Exception:
                    log_file = None  # 打不开就忽略文件写入

                while True:
                    if proc.stdout is None:
                        break
                    line = proc.stdout.readline()
                    if line == '' and proc.poll() is not None:
                        break

                    if line:
                        line_clean = line.strip()
                        output_lines.append(line_clean)

                        # 安全处理编码问题
                        try:
                            msg = f"[缓存] {line_clean}"
                            log_info(msg)
                            if log_callback:
                                log_callback(msg)
                            if log_file:
                                try:
                                    log_file.write(line)
                                    log_file.flush()
                                except Exception:
                                    pass
                        except UnicodeError:
                            # 如果有编码问题，使用安全的替换
                            safe_line = line_clean.encode('utf-8', errors='replace').decode('utf-8')
                            msg = f"[缓存] {safe_line}"
                            log_info(msg)
                            if log_callback:
                                log_callback(msg)
                            if log_file:
                                try:
                                    log_file.write(safe_line + "\n")
                                    log_file.flush()
                                except Exception:
                                    pass

                    # 检查超时
                    if time.time() - start_time > timeout:
                        proc.terminate()
                        raise subprocess.TimeoutExpired(command, timeout)

                # 检查返回码
                return_code = proc.poll()
                if return_code == 0:
                    log_success(f"命令执行成功 {mirror_info}")
                    if log_callback:
                        log_callback(f"[完成] 命令执行成功 {mirror_info}")
                    return True
                else:
                    error_text = '\n'.join(output_lines[-20:])  # 获取最后20行输出
                    last_error = f"命令执行失败，退出码: {return_code}\n最后输出:\n{error_text}"

                    # 检查是否为网络错误
                    if not self._is_network_error(error_text):
                        # 非网络错误，不重试
                        log_error(f"非网络错误，停止重试: {last_error}")
                        if log_callback:
                            log_callback(f"[错误] 非网络错误，停止重试")
                        return False

                    log_error(f"网络错误 {mirror_info}: {last_error}")
                    if log_callback:
                        log_callback(f"[网络错误] {mirror_info}: 检测到网络问题")

            except subprocess.TimeoutExpired:
                last_error = f"命令执行超时 ({timeout}秒)"
                log_error(f"超时 {mirror_info}: {last_error}")
                if log_callback:
                    log_callback(f"[超时] {mirror_info}: {last_error}")

            except Exception as e:
                last_error = f"命令执行异常: {str(e)}"
                log_error(f"异常 {mirror_info}: {last_error}")
                if log_callback:
                    log_callback(f"[异常] {mirror_info}: {last_error}")

            finally:
                # 确保关闭日志文件
                if 'log_file' in locals() and log_file:
                    try:
                        log_file.close()
                    except Exception:
                        pass

            # 如果不是最后一次尝试，等待后重试
            if attempt < self.max_retries:
                log_info(f"等待 {self.retry_delay} 秒后重试...")
                if log_callback:
                    log_callback(f"等待 {self.retry_delay} 秒后重试...")
                time.sleep(self.retry_delay)

        # 所有尝试都失败了
        log_error(f"所有重试都失败了，最后错误: {last_error}")
        if log_callback:
            log_callback(f"[失败] 所有重试都失败了")

        return False

    def cleanup(self):
        """清理环境变量"""
        if 'HF_ENDPOINT' in os.environ:
            del os.environ['HF_ENDPOINT']
            log_info("已清理HF镜像站环境变量")
