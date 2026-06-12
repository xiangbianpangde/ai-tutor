"""M-003 客户端入口 - Web 形态（FastAPI 静态资源挂载 + 浏览器启动）

> 对应模块: M-003 / sm003-web
> 关联接口: IC-001（服务启动，Web 形态作为其前端）
> 关联选型: TS-002 FastAPI / TS-001 Python
> 设计模式: Facade（Web 形态复用 M-001 的 FastAPI app）
> 来源标注: [DD-001:MD-003/FS-003] + [DD-M推断:StaticFiles 挂载 + 自动打开浏览器]

[文件职责]  Web 形态入口，挂载前端静态资源到 M-001 FastAPI app，启动时尝试打开浏览器。
[所属模块]  M-003（来自 DD-001）
[关联设计规范]  FS-003 / MD-003（来自 DD-001）

[功能描述]
  功能1: 挂载前端 HTML/CSS/JS 静态资源到 FastAPI app（路径 /）
  功能2: 启动时尝试自动打开默认浏览器（E00302 失败时降级为 CLI 提示）
  功能3: 暴露 `web_serve` 作为 pyproject scripts 入口

[输入输出]
  输入:  app: FastAPI（来自 M-001）
  输出:  None（原地修改 app 路由）

[依赖关系]
  依赖文件:  aitutor.app_factory（M-001 FastAPI app 工厂）
  被依赖文件:  aitutor.clients.__init__（re-export WebEntry / web_serve）

[注意事项]
  注意1: 浏览器启动失败不应阻塞服务启动（E00302 降级）
  注意2: 静态资源路径必须在白名单内（防路径穿越，CS 安全规范）
  注意3: 不在 Web 形态中实现业务逻辑，仅做静态资源与浏览器集成

[代码风格]  遵循 CS-AITutor-V3.1（来自 DD-001）
[创建日期]  2026-06-02
[修改历史]
  2026-06-02: DD-M-003 - 初始创建（仅注释骨架，无业务代码）
[作者]  DD-M-003-20260602
[来源标注]  [DD-001:MD-003/FS-003 sm003-web]
"""

# 标准库
import webbrowser
from pathlib import Path
from typing import Final

# 第三方库
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# 本地模块
# from aitutor.app_factory import build_app  # [DD-M推断:延迟到 web_serve 内部导入]


# ============================================================
# 模块级常量
# ============================================================

# 前端静态资源目录（相对项目根）
# [DD-M推断:约定 src/aitutor/clients/web/ 下的 static/ 目录]
_STATIC_DIR: Final[Path] = Path(__file__).parent / "web" / "static"

# 前端入口文件名
_INDEX_FILE: Final[str] = "index.html"


# ============================================================
# 类定义
# ============================================================


class WebEntry:
    """[类名] WebEntry
    [职责]  Web 形态入口封装，封装 FastAPI 静态资源挂载与浏览器启动。
    [关联设计规范] MD-003 sm003-web（来自 DD-001）

    [属性]
      属性1: html_path: str              前端 HTML 入口文件绝对路径
      属性2: static_dir: Path            静态资源目录
      属性3: open_browser: bool          启动时是否自动打开浏览器

    [方法列表]
      方法1: __init__() -> None          - 初始化路径与配置
      方法2: mount_static(app) -> None   - 挂载静态资源到 FastAPI app
      方法3: launch_browser(url) -> bool - 打开浏览器（失败返回 False）

    [状态机]  N/A

    [异常处理]
      异常1: E00302 浏览器未启动 - 降级 CLI 提示，不阻塞服务
    """

    # --------------------------------------------------------
    # 构造与初始化
    # --------------------------------------------------------

    def __init__(
        self,
        html_path: str | None = None,
        open_browser: bool = True,
    ) -> None:
        """[函数名] __init__
        [职责]  初始化 Web 形态入口，配置静态资源路径与浏览器启动策略。
        [关联接口契约]  N/A
        [参数说明]
          参数1: html_path str | None  可选 默认 None（即 _STATIC_DIR/_INDEX_FILE）  前端 HTML 入口路径
          参数2: open_browser bool     可选 默认 True                                启动时是否打开浏览器
        [返回值]  None
        [错误码]  无
        [前置条件]  _STATIC_DIR 存在（启动时校验，不存在则记录 WARN 不阻塞）
        [后置条件]  self.html_path / self.static_dir / self.open_browser 已设置
        [并发安全]  N/A
        [幂等性]  是
        [性能约束]  <5ms
        [来源标注]  [DD-001:MD-003 sm003-web]
        """
        # [DD-M推断:html_path 缺省时使用 _STATIC_DIR/_INDEX_FILE]
        self.html_path: str = html_path or str(_STATIC_DIR / _INDEX_FILE)
        self.static_dir: Path = _STATIC_DIR
        self.open_browser: bool = open_browser
        raise NotImplementedError  # 业务代码由 DD-S 实现

    # --------------------------------------------------------
    # 静态资源挂载
    # --------------------------------------------------------

    def mount_static(self, app: FastAPI) -> None:
        """[函数名] mount_static
        [职责]  将前端静态资源目录挂载到 FastAPI app 的根路径。
        [关联接口契约]  N/A
        [参数说明]
          参数1: app FastAPI 必填 来自 M-001 AppLauncher.build_app()
        [返回值]  None
        [错误码]  无
        [前置条件]  app 存在且未挂载根路径
        [后置条件]  GET / 返回 index.html，GET /static/* 返回静态资源
        [并发安全]  N/A（启动期调用一次）
        [幂等性]  否（重复挂载会抛异常）
        [性能约束]  <50ms
        [来源标注]  [DD-001:FS-003 clients/web.py]
        """
        # [DD-M推断:使用 FastAPI StaticFiles，挂载到 "/" 路径，html=True 自动 index]
        raise NotImplementedError  # 业务代码由 DD-S 实现

    # --------------------------------------------------------
    # 浏览器启动（带降级）
    # --------------------------------------------------------

    def launch_browser(self, url: str) -> bool:
        """[函数名] launch_browser
        [职责]  尝试打开默认浏览器访问指定 URL。
        [关联接口契约]  N/A
        [参数说明]
          参数1: url str 必填 形如 "http://127.0.0.1:8000" 的完整 URL
        [返回值]
          类型: bool
          描述: True=启动成功 / False=启动失败（已记录 WARN）
          特殊值: False 触发 E00302 降级 CLI 提示
        [错误码]
          错误码1: E00302 浏览器未启动  webbrowser.open 返回 False
        [前置条件]  无
        [后置条件]  浏览器已打开 / 失败已记录日志
        [并发安全]  N/A
        [幂等性]  否（每次调用会打开新标签）
        [性能约束]  <2s
        [来源标注]  [DD-001:MD-003 E00302]
        """
        # [DD-M推断:使用 stdlib webbrowser.open，失败时降级不阻塞]
        raise NotImplementedError  # 业务代码由 DD-S 实现


# ============================================================
# 模块级入口函数（pyproject scripts 入口）
# ============================================================


def web_serve(app: FastAPI | None = None) -> None:
    """[函数名] web_serve
    [职责]  Web 形态主入口，由 pyproject [project.scripts] aitutor-web 引用。
    [关联接口契约]  IC-001（服务启动）
    [参数说明]
      参数1: app FastAPI | None  可选 默认 None（即 build_app() 构造）  M-001 的 FastAPI app
    [返回值]  None
    [错误码]
      错误码1: E00302 浏览器未启动  降级 CLI 提示，不阻塞
    [前置条件]  M-001 配置就绪
    [后置条件]  静态资源已挂载 / 浏览器已尝试打开
    [并发安全]  N/A
    [幂等性]  否（启动 uvicorn 阻塞主线程）
    [性能约束]  启动 ≤30s（IC-001 约束）
    [示例]
      >>> # web_serve()  # 启动服务 + 打开浏览器
    [来源标注]  [DD-001:MD-003 web_serve + IC-001]
    """
    # [DD-M推断:app 缺省时调用 aitutor.app_factory.build_app() 构造]
    raise NotImplementedError  # 业务代码由 DD-S 实现
