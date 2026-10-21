"""
使用 PyInstaller 将 main.py 打成可执行包（默认 onedir，可选 onefile）。

前置：已安装依赖（pip install -r requirements.txt）且已安装 PyInstaller（已在 requirements.txt 中）。

用法（在项目根目录）：
  python build.py              # 先 npm run build 再打包
  python build.py --skip-npm   # 跳过前端构建（需已有 frontend/dist）
  python build.py --onefile    # 单文件模式（启动较慢）
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MAIN = ROOT / "main.py"
FRONTEND = ROOT / "frontend"
DIST_INDEX = FRONTEND / "dist" / "index.html"
DEFAULT_NAME = "liepin-helper-api"


def _pyinstaller_data_sep() -> str:
    return ";" if sys.platform == "win32" else ":"


def _run(cmd: list[str], cwd: Path | None = None) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.check_call(cmd, cwd=cwd)


def _ensure_pyinstaller() -> None:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("请先安装: pip install pyinstaller", file=sys.stderr)
        sys.exit(1)


def _npm_build() -> None:
    pkg = FRONTEND / "package.json"
    if not pkg.is_file():
        print(f"未找到 {pkg}，跳过前端构建。", file=sys.stderr)
        return
    npm = shutil.which("npm")
    if not npm:
        print("未找到 npm，请安装 Node.js 或将已构建的 frontend/dist 放入项目。", file=sys.stderr)
        sys.exit(1)
    if not (FRONTEND / "node_modules").is_dir():
        print("正在 frontend 目录执行 npm ci / npm install …")
        try:
            _run([npm, "ci"], cwd=FRONTEND)
        except subprocess.CalledProcessError:
            _run([npm, "install"], cwd=FRONTEND)
    _run([npm, "run", "build"], cwd=FRONTEND)


def _pyinstaller_args(
    *,
    onefile: bool,
    name: str,
    icon: Path | None,
) -> list[str]:
    sep = _pyinstaller_data_sep()
    cfg_dir = ROOT / "backend" / "config"
    if not cfg_dir.is_dir():
        print(f"缺少目录: {cfg_dir}", file=sys.stderr)
        sys.exit(1)

    opts: list[str] = [
        "-m",
        "PyInstaller",
        "--clean",
        "--noconfirm",
        f"--name={name}",
        f"--paths={ROOT}",
    ]

    if onefile:
        opts.append("--onefile")
    else:
        opts.append("--onedir")

    if icon and icon.is_file():
        opts.append(f"--icon={icon}")

    # 静态站与日志配置（与 main.py / logger 在 frozen 下的路径一致）
    opts.extend(
        [
            "--add-data",
            f"{FRONTEND / 'dist'}{sep}frontend/dist",
            "--add-data",
            f"{cfg_dir}{sep}backend/config",
        ]
    )

    # ASGI / Web 栈：动态加载较多，显式收集必要子模块
    for pkg in (
        "uvicorn",
        "starlette",
        "anyio",
        "pydantic",
        "multipart",
        "yaml",
    ):
        opts.extend(["--collect-all", pkg])

    # 业务侧：pandas / selenium 等已有 PyInstaller hook；避免 collect-all 拉入大量 tests。
    # Playwright 需要带上 driver/package，否则打包后 sync_playwright 可能找不到运行时资源。
    opts.extend(["--collect-all", "playwright"])

    # uvicorn 协议与循环实现
    for mod in (
        "uvicorn.loops.auto",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.lifespan.on",
        "multipart.multipart",
    ):
        opts.extend(["--hidden-import", mod])

    # 无控制台则看不到日志；保留控制台
    opts.append("--console")

    # 入口脚本放在末尾，符合 PyInstaller 习惯
    opts.append(str(MAIN))
    return opts


def main() -> None:
    parser = argparse.ArgumentParser(description="打包 liepin-helper-api（PyInstaller）")
    parser.add_argument(
        "--skip-npm",
        action="store_true",
        help="不执行 npm run build（需已存在 frontend/dist）",
    )
    parser.add_argument(
        "--onefile",
        action="store_true",
        help="单可执行文件（解压慢，调试不如 onedir 方便）",
    )
    parser.add_argument(
        "--name",
        default=DEFAULT_NAME,
        help=f"生成可执行文件名/目录名，默认 {DEFAULT_NAME}",
    )
    parser.add_argument(
        "--icon",
        type=Path,
        default=None,
        help="可选 .ico（Windows）或 .icns（macOS）图标路径",
    )
    args = parser.parse_args()

    if not MAIN.is_file():
        print(f"未找到入口: {MAIN}", file=sys.stderr)
        sys.exit(1)

    if not args.skip_npm:
        _npm_build()

    if not DIST_INDEX.is_file():
        print(
            f"缺少前端产物: {DIST_INDEX}。\n"
            "请先在前端目录执行 npm run build，或使用 --skip-npm 并手动准备好 dist。",
            file=sys.stderr,
        )
        sys.exit(1)

    _ensure_pyinstaller()
    py_args = _pyinstaller_args(onefile=args.onefile, name=args.name, icon=args.icon)
    _run([sys.executable, *py_args], cwd=ROOT)

    print()
    print("打包完成。")
    if args.onefile:
        if sys.platform == "win32":
            exe = ROOT / "dist" / f"{args.name}.exe"
        else:
            exe = ROOT / "dist" / args.name
    else:
        out = ROOT / "dist" / args.name
        if sys.platform == "win32":
            exe = out / f"{args.name}.exe"
        else:
            exe = out / args.name
    print(f"可执行文件: {exe}")
    print("默认监听 0.0.0.0:11100；无桌面环境请使用: --no-frontend")
    print()
    print("说明：生产测试请勿携带 .venv；在目标机用同版本 Python 或直接使用上述可执行文件。")


if __name__ == "__main__":
    main()
