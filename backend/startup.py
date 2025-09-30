#!/usr/bin/env python3
"""
EasyTuner FastAPI 后端启动脚本
"""

import sys
import os
import uvicorn
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
# sys.path.insert(0, str(project_root / "src"))  # 新架构不再需要
sys.path.insert(0, str(project_root / "backend"))

def main():
    """启动FastAPI服务器"""
    
    # 设置环境变量
    os.environ.setdefault("PYTHONPATH", str(project_root))
    
    # 启动服务器
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        reload_dirs=[str(Path(__file__).parent)],
        log_level="info",
        access_log=True,
        ws_ping_interval=20,
        ws_ping_timeout=20
    )

if __name__ == "__main__":
    main()