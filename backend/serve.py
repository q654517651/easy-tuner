"""
打包运行入口（无 reload）

用于 PyInstaller 打包为单文件 exe。
保持运行目录旁挂 runtime/ 与 workspace/ 目录。
"""

import uvicorn


def main():
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        log_level="info",
        access_log=True,
        ws_ping_interval=20,
        ws_ping_timeout=20,
        reload=False,
    )


if __name__ == "__main__":
    main()

