# Prompt Vault Vision

> **Pro 部署服务：299 元起**
>
> 如果你不想自己配置 Python、Node、GitHub Token、LM Studio / DeepSeek、SQLite 和本地启动环境，可以选择付费部署服务。服务内容包括本地运行环境配置、项目启动、基础功能检查和使用说明。需要部署支持可通过 GitHub Issues 或作者主页联系。

本地视觉 Prompt 资产管理器，用于持续沉淀 GitHub 上的视觉 Prompt、效果图、Web UI 组件仓库、Skill 仓库和相关证据链。

系统以 SQLite 作为主索引，图片和导出文件保存在本地目录中，前端通过 API 访问数据，不直接读取数据库文件。

## 核心能力

- GitHub 增量发现：按分类搜索图像生成、视频生成、Web UI、Skill 相关仓库。
- 仓库去重：URL 归一化、Fork 处理、相似内容判断、图片 hash 去重。
- Prompt 资产库：保存 Prompt、效果图、来源页面、匹配证据、筛选状态、翻译和标签。
- Web UI 资产库：收藏和检索前端组件库、设计规范仓库，并按画像得分排序。
- Skill 资产库：收藏和检索 AI Skill、Agent 工具、MCP 服务，并标注具体使用场景。
- 后台任务：支持定时搜索、仓库扫描任务、标注任务和运行记录。
- 本地 UI：React + TypeScript + Tailwind，提供瀑布流、抽屉详情、筛选、收藏和导出。

## 技术栈

- Backend：Python、FastAPI、SQLite
- Frontend：React、TypeScript、Vite、Tailwind CSS
- Data：SQLite、Markdown/JSON/CSV 导出、本地图片资产

## 目录结构

```text
backend/      FastAPI 后端、路由、服务、扫描和标注逻辑
frontend/     React 前端界面
data/         SQLite 数据库目录，本地运行时生成
assets/       图片、缩略图和来源页面缓存
exports/      Markdown、JSON、CSV 等导出文件
notes/        辅助说明和资源卡片
tests/        后端单元测试与集成测试
```

## 本地运行

后端：

```powershell
cd backend
python -m uvicorn app:app --host 127.0.0.1 --port 8001
```

前端：

```powershell
cd frontend
npm install
npm run dev
```

默认访问：

```text
http://127.0.0.1:5174
```

如需修改前端 API 地址，可在 `frontend/.env` 中配置：

```env
VITE_API_BASE_URL=http://127.0.0.1:8001
```

## GitHub 授权

推荐在 UI 中使用「连接 GitHub」完成授权。授权成功后，Token 会保存在本地认证目录中，该目录不会提交到 Git。

也可以在后端环境变量中手动配置：

```env
GITHUB_TOKEN=your_github_token
```

未配置 Token 时，GitHub 搜索任务会失败并写入日志，不会推进增量搜索时间。

## 本地数据说明

以下内容属于本地运行数据，不会提交到仓库：

- `data/*.db`
- `assets/images/*`
- `assets/thumbnails/*`
- `assets/source_pages/*`
- `exports/*`
- `backend/.auth/*`
- `.env`

仓库中只保留源码、测试和必要的 `.gitkeep` 文件。

## 验证

后端：

```powershell
python -m compileall backend
python -m pytest -q
```

前端：

```powershell
cd frontend
npm run build
```

## 定位

Prompt Vault Vision 不是普通收藏夹，而是一个长期可维护的本地视觉 Prompt 资产系统。它关注的是：

```text
Prompt
+ 效果图
+ 来源页面
+ 匹配证据
+ 翻译标签
+ 收藏筛选
+ SQLite 索引
+ 本地 UI 检索
```

## 免责声明

本项目仅用于个人学习、研究和本地资产管理。系统检索、整理或展示的 GitHub 仓库、Prompt、图片、截图、视频缩略图及其它资料均来自对应来源页面，版权、商标、License 和使用限制归原作者或权利方所有。

使用者在复用、分发、商用或二次创作任何 Prompt 与素材前，应自行核验来源链接、License、商用授权、隐私风险和平台规则。本项目不会替你自动取得商业授权，也不对第三方内容的合法性、准确性、完整性、可商用性或使用后果作出保证。

请勿使用本项目采集、整理、生成或传播违法违规、侵权、恶意、成人色情、血腥暴力、破解、恶意软件等内容。因使用本项目或相关数据产生的任何风险与责任，由使用者自行承担。
