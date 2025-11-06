# 🚀 Founder Buddy - Vercel 快速部署指南

## 📋 部署步骤总览

1. ✅ **后端部署** → Railway/Render（5分钟）
2. ✅ **前端部署** → Vercel（5分钟）
3. ✅ **连接前后端** → 配置环境变量（2分钟）

---

## 第一步：部署后端 API

### 选项 A: Railway（推荐，最简单）

1. 访问 [railway.app](https://railway.app)，用 GitHub 登录
2. 点击 **"New Project"** → **"Deploy from GitHub repo"**
3. 选择 `Victoria824/FounderBuddy`
4. 在 **Variables** 标签添加：
   ```
   OPENAI_API_KEY=your-openai-api-key
   ```
5. Railway 会自动部署，等待完成
6. 点击 **Settings** → **Generate Domain**，复制 URL（例如：`https://founder-buddy-production.up.railway.app`）

### 选项 B: Render（免费）

1. 访问 [render.com](https://render.com)，用 GitHub 登录
2. 点击 **"New +"** → **"Web Service"**
3. 连接仓库 `Victoria824/FounderBuddy`
4. 设置：
   - **Name**: `founder-buddy-backend`
   - **Build Command**: `pip install uv && uv sync`
   - **Start Command**: `uv run python src/run_service.py`
5. 在 **Environment** 添加 `OPENAI_API_KEY`
6. 点击 **Create Web Service**，等待部署
7. 复制分配的 URL

---

## 第二步：部署前端到 Vercel

1. 访问 [vercel.com](https://vercel.com)，用 GitHub 登录
2. 点击 **"Add New..."** → **"Project"**
3. 导入仓库 `Victoria824/FounderBuddy`
4. Vercel 会自动检测 Next.js，确认设置：
   - **Framework Preset**: Next.js ✅
   - **Root Directory**: `frontend` ✅
   - **Build Command**: `npm run build` ✅
   - **Output Directory**: `.next` ✅

5. 在 **Environment Variables** 添加：
   ```
   NEXT_PUBLIC_API_ENV=production
   VALUE_CANVAS_API_URL_PRODUCTION=https://your-backend-url-from-step-1
   ```
   ⚠️ **重要**：将 `your-backend-url-from-step-1` 替换为第一步获得的后端 URL

6. 点击 **"Deploy"**

7. 等待部署完成（约 2-3 分钟）

8. 访问 Vercel 提供的 URL，例如：`https://founder-buddy.vercel.app`

---

## 第三步：验证部署

1. ✅ 打开前端 URL
2. ✅ 打开浏览器开发者工具（F12）→ Network 标签
3. ✅ 发送一条测试消息
4. ✅ 检查 API 请求是否指向正确的后端 URL
5. ✅ 确认聊天功能正常工作

---

## 🔧 环境变量检查清单

### Vercel（前端）
- [ ] `NEXT_PUBLIC_API_ENV=production`
- [ ] `VALUE_CANVAS_API_URL_PRODUCTION=https://your-backend-url`

### Railway/Render（后端）
- [ ] `OPENAI_API_KEY=sk-...`

---

## 🐛 常见问题

### ❌ 前端显示 "Failed to fetch agents"

**原因**：后端 URL 配置错误或后端未运行

**解决**：
1. 检查 Vercel 环境变量中的 `VALUE_CANVAS_API_URL_PRODUCTION`
2. 确认后端服务正在运行（访问 `https://your-backend-url/health`）
3. 检查后端 URL 是否正确（不要有尾部斜杠）

### ❌ CORS 错误

**原因**：后端未允许前端域名

**解决**：后端代码应该已经配置了 CORS，如果还有问题，检查 `src/service/service.py` 中的 CORS 设置

### ❌ 构建失败

**原因**：依赖问题或配置错误

**解决**：
1. 检查 Vercel 构建日志
2. 确认 `frontend/package.json` 中的依赖正确
3. 尝试在本地运行 `cd frontend && npm install && npm run build` 测试

---

## 📚 详细文档

- [完整 Vercel 部署指南](./VERCEL_DEPLOYMENT.md)
- [后端部署详细指南](./BACKEND_DEPLOYMENT.md)

---

## ✅ 部署完成检查清单

- [ ] 后端服务正常运行（`/health` 返回 `{"status": "ok"}`）
- [ ] 前端可以访问
- [ ] 前端可以连接到后端 API
- [ ] 聊天功能正常工作
- [ ] 环境变量已正确配置

---

**🎉 完成！** 你的 Founder Buddy 应用现在已经部署到生产环境了！

