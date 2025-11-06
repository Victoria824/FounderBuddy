# 后端部署指南

## 🚀 快速部署到 Railway（推荐）

### 1. 准备工作

1. 访问 [railway.app](https://railway.app) 并登录（可以使用 GitHub 账户）
2. 点击 **"New Project"**
3. 选择 **"Deploy from GitHub repo"**
4. 选择 `Victoria824/FounderBuddy` 仓库

### 2. 配置 Railway

#### 环境变量设置

在 Railway 项目设置中添加以下环境变量：

**必需变量**：
```
OPENAI_API_KEY=your-openai-api-key
```

**可选变量**（根据需要）：
```
LANGFUSE_SECRET_KEY=your-langfuse-secret-key
LANGFUSE_PUBLIC_KEY=your-langfuse-public-key
LANGFUSE_HOST=https://cloud.langfuse.com
LANGFUSE_TRACING=true
```

#### 启动命令

Railway 会自动检测，但你可以手动设置：

**Start Command**: 
```bash
uv run python src/run_service.py
```

**Build Command**（如果需要）:
```bash
# Railway 会自动安装依赖
```

### 3. 获取部署 URL

部署完成后，Railway 会提供一个 URL，例如：
```
https://founder-buddy-production.up.railway.app
```

**重要**：记下这个 URL，需要在 Vercel 的前端环境变量中使用。

### 4. 配置 CORS（如果需要）

如果遇到 CORS 错误，需要在后端代码中添加 CORS 中间件（通常已经配置）。

## 🐳 使用 Docker 部署（可选）

### 创建 Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装 uv
RUN pip install uv

# 复制项目文件
COPY . .

# 安装依赖
RUN uv sync

# 暴露端口
EXPOSE 8080

# 启动服务
CMD ["uv", "run", "python", "src/run_service.py"]
```

### 使用 Docker Compose

```yaml
version: '3.8'

services:
  backend:
    build: .
    ports:
      - "8080:8080"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    env_file:
      - .env
```

## 🌐 部署到 Render

### 1. 创建 Web Service

1. 访问 [render.com](https://render.com)
2. 点击 **"New +"** → **"Web Service"**
3. 连接 GitHub 仓库 `Victoria824/FounderBuddy`

### 2. 配置设置

- **Name**: `founder-buddy-backend`
- **Environment**: `Python 3`
- **Build Command**: `pip install uv && uv sync`
- **Start Command**: `uv run python src/run_service.py`
- **Plan**: 选择免费或付费计划

### 3. 环境变量

在 Render 的 Environment 标签中添加：
```
OPENAI_API_KEY=your-key
```

## 🔧 部署到 Fly.io

### 1. 安装 Fly CLI

```bash
curl -L https://fly.io/install.sh | sh
```

### 2. 登录并初始化

```bash
fly auth login
fly launch
```

### 3. 配置 fly.toml

```toml
app = "founder-buddy"
primary_region = "iad"

[build]

[env]
  PORT = "8080"

[[services]]
  internal_port = 8080
  protocol = "tcp"

  [[services.ports]]
    port = 80
    handlers = ["http"]
    force_https = true

  [[services.ports]]
    port = 443
    handlers = ["tls", "http"]
```

### 4. 设置环境变量

```bash
fly secrets set OPENAI_API_KEY=your-key
```

### 5. 部署

```bash
fly deploy
```

## 📋 环境变量清单

| 变量名 | 说明 | 必需 | 默认值 |
|--------|------|------|--------|
| `OPENAI_API_KEY` | OpenAI API 密钥 | ✅ | - |
| `LANGFUSE_SECRET_KEY` | Langfuse 密钥（用于追踪） | ❌ | - |
| `LANGFUSE_PUBLIC_KEY` | Langfuse 公钥 | ❌ | - |
| `LANGFUSE_HOST` | Langfuse 主机地址 | ❌ | `https://cloud.langfuse.com` |
| `LANGFUSE_TRACING` | 是否启用追踪 | ❌ | `false` |
| `PORT` | 服务端口 | ❌ | `8080` |

## ✅ 验证部署

部署完成后，访问：

```
https://your-backend-url.com/health
```

应该返回：
```json
{"status": "ok"}
```

## 🔗 连接前端

在 Vercel 的环境变量中设置：

```
VALUE_CANVAS_API_URL_PRODUCTION=https://your-backend-url.com
```

## 🐛 常见问题

### 问题 1: 端口错误

**解决方案**：
- Railway/Render 会自动设置 `PORT` 环境变量
- 确保代码使用 `os.getenv('PORT', '8080')` 读取端口

### 问题 2: 依赖安装失败

**解决方案**：
- 确保使用 Python 3.11+
- 检查 `pyproject.toml` 中的依赖版本

### 问题 3: 服务无法启动

**解决方案**：
- 检查日志输出
- 确认环境变量已正确设置
- 验证 `src/run_service.py` 文件存在

## 📚 推荐平台对比

| 平台 | 免费额度 | 优点 | 缺点 |
|------|---------|------|------|
| **Railway** | $5/月 | 简单易用，自动部署 | 免费额度有限 |
| **Render** | 免费 | 完全免费，简单 | 服务会休眠 |
| **Fly.io** | 免费 | 全球边缘部署 | 配置较复杂 |
| **Heroku** | 付费 | 成熟稳定 | 不再有免费层 |

**推荐**：Railway 或 Render（根据预算选择）

