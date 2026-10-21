# 运行与配置

## 先确认环境与权限

开源版先阅读 [自有服务配置](SERVICE_CONFIGURATION.md)。默认业务服务域名为 `.invalid`，模型和用户标识为占位符。离线测试可以直接运行，真实模型、人才库与完整平台联调需要自行接入兼容服务。

此仓库包含现有应用源码，不提供外部模型或人才数据库服务端。真实运行需要获得相应平台账号和业务服务授权。不要为测试直接启动批量沟通或上传任务。

三个 Python 模块各自包含依赖版本，建议分别建立 Python 3.12 虚拟环境，不要混装到同一环境。前端建议使用 Node.js 22.12+，按各模块 package-lock.json 安装依赖。这里是仓库整理后的操作入口，完整安装与平台联调并未因此自动通过；验证范围见 [VALIDATION](VALIDATION.md)。

所有命令从仓库根目录开始。启动后端前先完成对应前端构建，否则 FastAPI 静态目录可能不存在。

## Chrome 扩展

1. 打开 Chrome 扩展管理页并开启开发者模式。
2. 点击“加载已解压的扩展程序”，选择 `apps/extension`。
3. 阅读权限提示；该扩展当前申请较广泛的页面、Cookie 和脚本权限。
4. 使用有授权的测试账号和无个人信息的数据验证单个功能。

扩展不需要 npm 构建。历史业务截图未上传，帮助页保留文字提示。开源版不提供外部模型和人才服务，必须配置自己的兼容服务。

## 脉脉

```sh
cd apps/maimai
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cd web_gui
npm ci
npm run build
cd ..
python main.py --no-frontend
```

默认地址：`http://127.0.0.1:23333/`。程序使用已构建的 `web_gui/dist` 或发行版 Web 目录。

本地状态、简历和日志可能写入 `resource/manager.pkl`、`save/` 和 `log/`，都不应提交。只加载可信的 pickle 状态文件。

## 智联

```sh
cd apps/zhilian
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
cd frontend
npm ci
npm run build
cd ..
python main.py --no-frontend
```

默认地址：`http://127.0.0.1:11451/`。`.env.example` 默认关闭 HTML 诊断导出，避免无意产生含个人信息的调试文件。

账户及搜索策略通过原有界面配置。外部模型接口和 bot 配置位于 `backend/core/config/`；开源版提供离线配置替换工具，见 [服务配置](SERVICE_CONFIGURATION.md)。

## 猎聘

```sh
cd apps/liepin
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
cd frontend
npm ci
npm run build
cd ..
python main.py --no-frontend
```

默认地址：`http://127.0.0.1:11100/`。

若使用备注相关浏览器能力，按 `.env.example` 和原模块文档配置专用浏览器 profile；示例已移除个人电脑路径。Selenium / Playwright 相关功能可能需要匹配的本地浏览器或驱动，本次未安装浏览器驱动或进行登录。

## Windows 对应命令

上面的 `python3.12 -m venv .venv` 可替换为 `py -3.12 -m venv .venv`；激活命令替换为 `.venv\Scripts\Activate.ps1`。PowerShell 复制配置使用 `Copy-Item .env.example .env`。其余 Python 和 npm 命令保持一致。

原应用含 Windows 使用路径和浏览器依赖，不能仅因纯 Python 文件语法检查通过就视为已经全面兼容 macOS / Linux。

## 离线检查入口

这些命令不要求真实账号，仍应先核查测试中的 fixture 和 mock；避免执行库文件中的临时在线调试代码。

```sh
# 扩展已有测试
cd apps/extension
node --test tests/*.test.js
```

```sh
# 猎聘最高学历确定性规则测试（标准库即可）
cd apps/liepin
python -m unittest discover -s tests -p test_highest_education.py
```

其他 Python 测试需要对应模块依赖。完整历史测试可能依赖原项目未随 ZIP 提供的 fixture，具体以验证记录为准。

## 本地服务安全

原入口包含监听 `0.0.0.0` 的配置。浏览器使用 localhost 访问并不意味着服务只监听本机；请用防火墙/隔离网络限制访问，不要做端口映射或直接公开部署。详见 [SECURITY](../SECURITY.md)。
