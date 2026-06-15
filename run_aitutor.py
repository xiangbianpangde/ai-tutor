"""AI-Tutor 后端打包入口（M-015 / Nuitka onedir 用）。

为何不直接编译 backend/main.py：它用相对导入（`from .app import …`），被 Nuitka 当作
顶层脚本编译时丢失 `backend` 包上下文 → `ImportError: attempted relative import`。
本启动器用**绝对导入**，Nuitka standalone 顺着 `backend.*` 跟踪全部依赖，规避该坑。

开发期等价于 `python -m backend.main`。
"""
from backend.main import main

if __name__ == "__main__":
    main()
