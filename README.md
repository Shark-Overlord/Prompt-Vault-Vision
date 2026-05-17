# Visual Prompt Library

本地视觉 Prompt 资产管理器。系统以 SQLite 为主索引，保存 GitHub 资源、Prompt 与效果图对应关系、来源页面、效果评价、筛选结论、标签和导出数据。

## 当前能力

- FastAPI 后端，前后端完全分离。
- SQLite 数据库：`data/visual_prompt_library.db`。
- GitHub 增量搜索：先读 `search_state`，按 `created:>=` 和 `pushed:>=` 搜索；完整成功后才推进搜索时间。
- 去重：GitHub URL 归一化、canonical_url 唯一约束、Fork 跳过、图片 hash 去重。
- 图片资产：保存到 `assets/images`，缩略图保存到 `assets/thumbnails`。
- React + TypeScript + Tailwind UI：Dashboard、资源库、Prompt 瀑布流、待复查、搜索、导出。
- 导出：Markdown、JSON、CSV、桌面 AI Skill 数据。

## 运行

后端使用你的 `xh` 环境：

```powershell
cd I:\小工具\visual_prompt_library\backend
D:\anaconda3\envs\xh\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000
```

前端：

```powershell
cd I:\小工具\visual_prompt_library\frontend
npm run dev -- --port 5173
```

访问：

```text
http://127.0.0.1:5173
```

## GitHub Token

推荐在 UI 里点击「连接 GitHub」，使用 GitHub OAuth Device Flow 授权。第一次使用需要一个 GitHub OAuth App Client ID：

1. 打开 GitHub Developer settings，创建 OAuth App。
2. 启用 Device Flow。
3. 把 Client ID 填入本地 UI 的「连接 GitHub」弹窗。
4. 点击「连接 GitHub」，在浏览器中完成授权。
5. 后端会把 access token 保存到 `backend/.auth/github_token.json`，该目录已加入 `.gitignore`。

也可以复制 `backend/.env.example` 为 `backend/.env`，手动填写：

```env
GITHUB_TOKEN=你的 GitHub Token
```

没有授权或 token 时，`POST /api/search/github` 会返回 `needs_token`，不会推进 `search_state`。

## 验证

```powershell
cd I:\小工具\visual_prompt_library
D:\anaconda3\python.exe -m pytest -q

cd I:\小工具\visual_prompt_library\frontend
npm run build
```

## 目录约定

- `backend/routes`：API 路由，只做参数接收和服务调用。
- `backend/services`：GitHub 搜索、去重、Prompt 处理、导出。
- `backend/utils`：图片下载、hash、缩略图。
- `frontend/src/components`：可复用 UI 组件。
- `frontend/src/pages`：页面级布局。
- `exports`：日报、精选库和结构化导出。
