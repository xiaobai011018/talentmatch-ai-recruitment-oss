#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生产测试打包脚本：构建 web_gui 前端，运行 PyInstaller，并把静态站点复制到产物目录。

运行环境要求：Node.js + npm、已安装 requirements.txt（含 pyinstaller）、Windows 下生成 main.exe。

产物目录与 main.spec 中 COLLECT 的 name 一致；若修改 spec 中的名称，请同步更新 PYINSTALLER_APP_NAME。
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent
WEB_GUI = ROOT / "web_gui"
FRONTEND_DIST = WEB_GUI / "dist"
SPEC_FILE = ROOT / "main.spec"
# 须与 main.spec 里 COLLECT(..., name='...') 保持一致
PYINSTALLER_APP_NAME = "MaiMaiHelper_v2.1.55"


def _run(cmd: list[str], cwd: Path, *, env: Optional[dict[str, str]] = None) -> None:
    print(f"[build] cwd={cwd}")
    print(f"[build] {' '.join(cmd)}")
    subprocess.run(cmd, cwd=cwd, env=env, check=True)


def _find_pyinstaller_output() -> Path:
    base = ROOT / "dist"
    if not base.is_dir():
        raise FileNotFoundError(f"未找到 {base}，请先确认 PyInstaller 已成功执行")
    expected = base / PYINSTALLER_APP_NAME
    if expected.is_dir() and (expected / "main.exe").is_file():
        return expected
    for p in base.iterdir():
        if p.is_dir() and (p / "main.exe").is_file():
            print(f"[build] 警告: 使用检测到的产物目录 {p.name}（与 PYINSTALLER_APP_NAME 不一致时请改 build.py 或 main.spec）")
            return p
    raise FileNotFoundError(f"在 {base} 下未找到包含 main.exe 的目录")


def build_frontend(skip: bool) -> None:
    if skip:
        print("[build] 跳过前端构建")
        if not FRONTEND_DIST.is_dir() or not any(FRONTEND_DIST.iterdir()):
            raise FileNotFoundError(f"{FRONTEND_DIST} 不存在或为空，请先构建前端或去掉 --skip-frontend")
        return
    npm = shutil.which("npm")
    if not npm:
        raise RuntimeError("未找到 npm，请安装 Node.js 并确保 npm 在 PATH 中")
    if (WEB_GUI / "package-lock.json").is_file():
        _run([npm, "ci"], WEB_GUI)
    else:
        _run([npm, "install"], WEB_GUI)
    _run([npm, "run", "build"], WEB_GUI)


def build_pyinstaller(skip: bool, clean: bool) -> Path:
    if skip:
        print("[build] 跳过 PyInstaller")
        return _find_pyinstaller_output()
    cmd = [sys.executable, "-m", "PyInstaller"]
    if clean:
        cmd.append("--clean")
    cmd.extend(["-y", str(SPEC_FILE)])
    _run(cmd, ROOT)
    return _find_pyinstaller_output()


def copy_web_to_bundle(app_dir: Path) -> None:
    target = app_dir / "web"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(FRONTEND_DIST, target)
    print(f"[build] 已复制前端静态文件 -> {target}")


def make_zip(app_dir: Path, out: Optional[Path]) -> None:
    if out is None:
        out = ROOT / "dist" / f"{app_dir.name}_prod_test.zip"
    out.parent.mkdir(parents=True, exist_ok=True)
    base_name = str(out.with_suffix(""))
    archive = shutil.make_archive(base_name, "zip", root_dir=app_dir.parent, base_dir=app_dir.name)
    print(f"[build] 已生成压缩包: {archive}")


def main() -> int:
    parser = argparse.ArgumentParser(description="MaimaiHelper 生产测试打包")
    parser.add_argument("--skip-frontend", action="store_true", help="跳过 npm build（需已有 web_gui/dist）")
    parser.add_argument("--skip-pyinstaller", action="store_true", help="跳过 PyInstaller（使用已有 dist 目录）")
    parser.add_argument("--no-clean", action="store_true", help="不传 PyInstaller --clean")
    parser.add_argument("--zip", action="store_true", help="打包完成后将产物目录打成 zip")
    parser.add_argument(
        "--zip-output",
        type=Path,
        default=None,
        help="zip 输出路径（默认 dist/<产物名>_prod_test.zip）",
    )
    args = parser.parse_args()

    if not SPEC_FILE.is_file():
        print(f"[build] 错误: 找不到 {SPEC_FILE}", file=sys.stderr)
        return 1

    try:
        build_frontend(args.skip_frontend)
        app_dir = build_pyinstaller(args.skip_pyinstaller, clean=not args.no_clean)
        copy_web_to_bundle(app_dir)
        print(f"[build] 完成。请将整个文件夹部署到测试机：{app_dir}")
        print("[build] 运行前请在同目录 resource/ 下放置 chromedriver.exe（及所需配置）；首次运行会自动创建 log/、save/ 等。")
        if args.zip:
            make_zip(app_dir, args.zip_output)
    except (subprocess.CalledProcessError, FileNotFoundError, RuntimeError) as e:
        print(f"[build] 失败: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
