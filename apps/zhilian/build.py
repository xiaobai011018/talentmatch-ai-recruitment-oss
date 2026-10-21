import os
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent


def build_frontend():
    """如果 frontend 存在则构建前端，否则跳过。"""
    fe_dir = PROJECT_ROOT / "frontend"
    if not fe_dir.exists():
        print("未检测到 frontend 目录，跳过前端构建。")
        return

    print("开始构建前端...")
    prev_cwd = Path.cwd()
    try:
        os.chdir(fe_dir)

        # 尝试定位 npm
        npm_exec = shutil.which("npm")
        if not npm_exec and os.name == "nt":
            npm_exec = shutil.which("npm.cmd") or shutil.which("npm.ps1")

        # 如果找到了可执行文件，则直接调用；在 Windows 上 prefer shell=True
        if npm_exec:
            print(f"使用 npm 可执行文件: {npm_exec}")
            try:
                if os.name == "nt":
                    # Windows 下使用 shell=True 可以正确执行 npm.cmd / npm.ps1
                    subprocess.run("npm install", shell=True, check=True)
                    subprocess.run("npm run build", shell=True, check=True)
                else:
                    subprocess.run([npm_exec, "install"], check=True)
                    subprocess.run([npm_exec, "run", "build"], check=True)
            except Exception as e:
                print("npm 命令执行失败：npm install && npm run build")
                raise
        else:
            # 最后尝试使用 shell 去调用（某些 shell 配置下 npm 仅能通过 shell 找到）
            print("未直接找到 npm 可执行文件，尝试使用 shell 调用 npm（可能依赖 shell 环境）。")
            try:
                subprocess.run("npm install", shell=True, check=True)
                subprocess.run("npm run build", shell=True, check=True)
            except Exception as e:
                raise RuntimeError(f"未找到 npm 或 npm 调用失败，请先安装 Node.js 与 npm，或确保 npm 在 PATH 中。详细错误: {e}")

        print("前端构建完成。")
    finally:
        os.chdir(prev_cwd)


def copy_resources():
    """复制前端构建产物、后端配置、以及 resource 到 resources 目录。"""
    print("复制资源文件...")
    res_dir = PROJECT_ROOT / "resources"
    dist_src = PROJECT_ROOT / "frontend" / "dist"
    config_src = PROJECT_ROOT / "backend" / "core" / "config"
    resource_src = PROJECT_ROOT / "backend" / "core" / "resource"

    # 删除旧 resources
    if res_dir.exists():
        shutil.rmtree(res_dir)

    # 创建新目录
    (res_dir / "dist").mkdir(parents=True, exist_ok=True)
    (res_dir / "config").mkdir(parents=True, exist_ok=True)
    (res_dir / "resource").mkdir(parents=True, exist_ok=True)

    # 复制前端 dist
    if dist_src.exists():
        shutil.copytree(dist_src, res_dir / "dist", dirs_exist_ok=True)

    # 复制 config
    if config_src.exists():
        shutil.copytree(config_src, res_dir / "config", dirs_exist_ok=True)

    # 复制 resource（这里包含你需要的 zhilian_region_code.json）
    if resource_src.exists():
        shutil.copytree(resource_src, res_dir / "resource", dirs_exist_ok=True)
        print("已复制 backend/core/resource → resources/resource")
    else:
        print("警告：未找到 backend/core/resource")


def build_executable():
    """使用 PyInstaller 打包，自动处理不同平台的 add-data 分隔符。

    通过 `python -m PyInstaller` 调用，避免依赖 PATH 中的 pyinstaller 可执行文件。
    """
    print("开始打包可执行文件...")

    res_dir = PROJECT_ROOT / "resources" / "dist"
    cfg_dir = PROJECT_ROOT / "resources" / "config"
    resource_dir = PROJECT_ROOT / "resources" / "resource"

    add_data = []
    # PyInstaller 在 Windows 使用分号 (os.pathsep)，在 POSIX 上使用冒号
    sep = os.pathsep

    if res_dir.exists():
        add_data.append(f"{str(res_dir)}{sep}resources/dist")
    if cfg_dir.exists():
        add_data.append(f"{str(cfg_dir)}{sep}backend/core/config")
    if resource_dir.exists():
        add_data.append(f"{str(resource_dir)}{sep}backend/core/resource")

    # 尝试自动将 requirements.txt 中的包名转换为 PyInstaller 的 collect/hidden-import 参数，
    # 以尽可能把依赖打进可执行文件。这会尽量把顶层包的子模块都收集进来。
    collect_submodules = []
    req_file = PROJECT_ROOT / "requirements.txt"
    if req_file.exists():
        # requirements.txt 可能使用不同编码（例如 UTF-16 带 BOM），尝试多种编码回退
        encodings_to_try = ("utf-8", "utf-8-sig", "utf-16", "latin-1")
        lines = None
        for enc in encodings_to_try:
            try:
                with req_file.open(encoding=enc) as f:
                    lines = f.readlines()
                break
            except UnicodeDecodeError:
                continue
        if lines is None:
            # 最后回退为二进制读取并以 latin-1 安全解码
            with req_file.open("rb") as f:
                raw = f.read()
            lines = raw.decode("latin-1", errors="ignore").splitlines()

        try:
            for line in lines:
                pkg = line.strip()
                if not pkg or pkg.startswith("#"):
                    continue
                # 支持多种版本约束写法，抽取包名
                for sepchar in ("==", "~=", ">=", "<=", "!=", ">", "<", "==="):
                    if sepchar in pkg:
                        pkg = pkg.split(sepchar)[0].strip()
                        break
                # 有时 requirements 中会带上 extras or markers，用 ';' 分隔，先取前半部分
                pkg = pkg.split(";")[0].strip()
                if pkg:
                    collect_submodules.append(pkg)
        except Exception:
            collect_submodules = []

    # 始终包含本地项目包 backend
    if "backend" not in collect_submodules:
        collect_submodules.insert(0, "backend")

    # 默认构建为有控制台的可执行文件，这样日志会输出到终端。
    # 如果需要无窗口（windowed）模式，可传入 environment 变量 BUILD_WINDOWED=1 或在脚本中设置 windowed=True。
    windowed = os.environ.get("BUILD_WINDOWED", "0") in ("1", "true", "True")
    cmd = [sys.executable, "-m", "PyInstaller", "--name=ZhiLianAuto"]
    if windowed:
        cmd.append("--noconsole")
    for item in add_data:
        cmd.extend(["--add-data", item])

    # 把 collect_submodules 转换为 PyInstaller 参数
    if collect_submodules:
        # 去重并按稳定顺序添加
        seen = set()
        for pkg in collect_submodules:
            if pkg and pkg not in seen:
                seen.add(pkg)
                # 使用 --collect-submodules 来收集包的所有子模块
                cmd.extend(["--collect-submodules", pkg])

    # 清理旧的 spec 文件名（PyInstaller 会生成 <name>.spec）
    spec_file = PROJECT_ROOT / "ZhiLianAuto.spec"
    if spec_file.exists():
        try:
            spec_file.unlink()
        except Exception:
            print(f"警告：无法删除旧的 spec 文件 {spec_file}")

    cmd.append(str(PROJECT_ROOT / "main.py"))

    # 如果项目里存在 .venv，优先使用该虚拟环境的 Python 去运行 PyInstaller，
    # 这样能保证打包器可见虚拟环境里安装的依赖（如 uvicorn/fastapi 等）。
    venv_python = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
    builder_python = str(venv_python) if venv_python.exists() else sys.executable

    print("运行 PyInstaller: ")
    print(" ".join(cmd))

    # 确保构建使用的 Python 环境里安装了 pyinstaller
    try:
        subprocess.run([builder_python, "-m", "pip", "install", "pyinstaller"], check=True)
        # altgraph 会 import pkg_resources（与 requirements.txt 一致：setuptools<81）
        subprocess.run(
            [builder_python, "-m", "pip", "install", "setuptools>=70.0.0,<81.0.0"],
            check=True,
        )
    except subprocess.CalledProcessError:
        print(f"自动在 {builder_python} 中安装 pyinstaller/setuptools 失败，请手动安装后重试。")
        raise

    try:
        subprocess.run([builder_python] + cmd[1:], check=True)
        print("打包完成！ 输出目录: dist/ZhiLianAuto（或 dist/ZhiLianAuto.exe）")
    except subprocess.CalledProcessError as e:
        print("PyInstaller 执行失败。请确认构建环境与依赖是否正确。")
        raise


def clean_old_builds():
    # 删除 PyInstaller 的旧构建输出
    for name in ("dist", "build"):
        path = PROJECT_ROOT / name
        if path.exists():
            print(f"删除旧目录: {path}")
            shutil.rmtree(path)


def main():
    try:
        clean_old_builds()
        build_frontend()
        copy_resources()
        build_executable()
    except Exception as e:
        print(f"构建失败：{e}")
        sys.exit(1)


if __name__ == "__main__":
    main()