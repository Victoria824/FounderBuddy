# Vercel 部署指南

## 📋 前置要求

1. **GitHub 账户** - 代码已上传到 GitHub
2. **Vercel 账户** - 访问 [vercel.com](https://vercel.com) 注册/登录
3. **后端 API** - 需要先部署后端服务（见下文）

## 🚀 部署步骤

### 1. 连接 GitHub 仓库到 Vercel

1. 访问 [vercel.com](https://vercel.com)
2. 点击 **"Add New..."** → **"Project"**
3. 导入 GitHub 仓库 `Victoria824/FounderBuddy`
4. Vercel 会自动检测到 Next.js 项目

### 2. 配置项目设置

在 Vercel 项目设置中：

**Root Directory**: `frontend`

**Build Command**: `npm run build`（Vercel 会自动检测）

**Output Directory**: `.next`（Vercel 会自动检测）

**Install Command**: `npm install`（Vercel 会自动检测）

### 3. 配置环境变量

在 Vercel 项目设置 → **Environment Variables** 中添加：

#### 必需的环境变量：

```
NEXT_PUBLIC_API_ENV=production
VALUE_CANVAS_API_URL_PRODUCTION=https://your-backend-api-url.com
```

#### 可选的环境变量：

```
VALUE_CANVAS_API_TOKEN=your-api-token-if-needed
```

**注意**：
- `NEXT_PUBLIC_API_ENV` 必须设置为 `production`（不是 `local`）
- `VALUE_CANVAS_API_URL_PRODUCTION` 是你的后端 API URL（见后端部署部分）

### 4. 部署

点击 **"Deploy"** 按钮，Vercel 会自动：
1. 安装依赖
2. 构建项目
3. 部署到全球 CDN

部署完成后，你会得到一个 URL，例如：`https://founder-buddy.vercel.app`

## 🔧 后端 API 部署

前端需要连接到后端 API。你可以选择以下平台之一部署后端：

### 选项 1: Railway（推荐）

1. 访问 [railway.app](https://railway.app)
2. 连接 GitHub 仓库
3. 选择 `FounderBuddy` 仓库
4. 设置启动命令：`uv run python src/run_service.py`
5. 配置环境变量（从 `.env` 文件）
6. Railway 会自动分配一个 URL，例如：`https://founder-buddy-production.up.railway.app`

### 选项 2: Render

1. 访问 [render.com](https://render.com)
2. 创建新的 Web Service
3. 连接 GitHub 仓库
4. 设置：
   - **Build Command**: `pip install -r requirements.txt`（如果有）
   - **Start Command**: `uv run python src/run_service.py`
   - **Environment**: Python 3

### 选项 3: Fly.io

1. 安装 Fly CLI: `curl -L https://fly.io/install.sh | sh`
2. 在项目根目录运行：`fly launch`
3. 按照提示配置

### 选项 4: Heroku

1. 创建 `Procfile`（已存在）
2. 在 Heroku 创建应用
3. 连接 GitHub 并部署

## 🔗 连接前后端

部署后端后，在 Vercel 的环境变量中设置：

```
VALUE_CANVAS_API_URL_PRODUCTION=https://your-backend-url.com
```

**重要**：确保后端 URL 不包含尾部斜杠 `/`

## ✅ 验证部署

1. 访问 Vercel 提供的 URL
2. 打开浏览器开发者工具（F12）
3. 检查 Network 标签，确认 API 请求指向正确的后端 URL
4. 测试聊天功能

## 🔄 自动部署

Vercel 会自动：
- 监听 GitHub 的 `main` 分支
- 当你 push 代码时自动重新部署
- 为每个 Pull Request 创建预览部署

## 📝 环境变量说明

| 变量名 | 说明 | 必需 | 示例 |
|--------|------|------|------|
| `NEXT_PUBLIC_API_ENV` | API 环境（`local` 或 `production`） | ✅ | `production` |
| `VALUE_CANVAS_API_URL_PRODUCTION` | 生产环境后端 API URL | ✅ | `https://api.example.com` |
| `VALUE_CANVAS_API_TOKEN` | API 认证 Token（如果需要） | ❌ | `your-token` |

## 🐛 常见问题

### 问题 1: 构建失败

**解决方案**：
- 检查 `frontend/package.json` 中的依赖是否正确
- 确保 Node.js 版本兼容（Vercel 默认使用 Node.js 18+）

### 问题 2: API 请求失败

**解决方案**：
- 检查后端 URL 是否正确
- 确认后端服务正在运行
- 检查 CORS 设置（后端需要允许 Vercel 域名）

### 问题 3: 环境变量不生效

**解决方案**：
- 确保变量名正确（区分大小写）
- 重新部署项目
- 检查变量是否设置为所有环境（Production, Preview, Development）

## 📚 更多资源

- [Vercel 文档](https://vercel.com/docs)
- [Next.js 部署指南](https://nextjs.org/docs/deployment)
- [Railway 文档](https://docs.railway.app)

