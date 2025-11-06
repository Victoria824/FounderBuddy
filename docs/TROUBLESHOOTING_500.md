# 500 错误排查指南

## 🔍 问题诊断

看到 500 错误时，需要检查以下几个方面：

### 1. 检查后端服务是否运行

在浏览器访问：
```
https://your-railway-url.com/health
```

应该返回：
```json
{"status":"ok"}
```

如果无法访问或返回错误，说明后端服务没有正常运行。

### 2. 检查环境变量配置

在 Vercel 中确认：
- ✅ `NEXT_PUBLIC_API_ENV` = `production`
- ✅ `VALUE_CANVAS_API_URL_PRODUCTION` = 完整的后端 URL（**不要**包含尾部斜杠）

**重要**：确保 URL 格式正确：
- ✅ 正确：`https://founder-buddy-production.up.railway.app`
- ❌ 错误：`https://founder-buddy-production.up.railway.app/`（有尾部斜杠）

### 3. 检查后端日志

在 Railway 项目页面：
1. 点击你的服务
2. 查看 **Logs** 标签
3. 查看是否有错误信息

### 4. 检查 Vercel 函数日志

在 Vercel 项目页面：
1. 点击最新的部署
2. 查看 **Functions** 标签
3. 点击 `/api/chat` 函数
4. 查看日志输出

### 5. 常见问题

#### 问题 A: 后端 URL 不正确

**症状**：Vercel 函数日志显示 "fetch failed" 或 "ECONNREFUSED"

**解决**：
1. 确认 Railway URL 是否正确
2. 在浏览器直接访问后端 URL 的 `/health` 端点
3. 如果无法访问，检查 Railway 服务状态

#### 问题 B: 后端服务未启动

**症状**：无法访问后端 URL

**解决**：
1. 检查 Railway 服务是否正在运行
2. 查看 Railway 日志，确认服务启动成功
3. 确认环境变量（特别是 `OPENAI_API_KEY`）已配置

#### 问题 C: CORS 错误

**症状**：浏览器控制台显示 CORS 相关错误

**解决**：
- 后端已添加 CORS 配置，应该不会出现此问题
- 如果仍有问题，检查后端是否已重新部署

#### 问题 D: 认证问题

**症状**：后端返回 401 Unauthorized

**解决**：
- 如果后端配置了 `AUTH_SECRET`，需要在 Vercel 配置 `VALUE_CANVAS_API_TOKEN`
- 或者移除后端的认证要求

## 🔧 调试步骤

### 步骤 1: 测试后端连接

在本地终端运行：
```bash
curl https://your-railway-url.com/health
```

应该返回 `{"status":"ok"}`

### 步骤 2: 测试后端 API

```bash
curl -X POST https://your-railway-url.com/founder-buddy/invoke \
  -H "Content-Type: application/json" \
  -d '{"message": "hello", "user_id": 1}'
```

### 步骤 3: 检查 Vercel 环境变量

1. 在 Vercel 项目设置中查看环境变量
2. 确认所有变量都已设置为 "All Environments"
3. 确认值正确（特别是 URL 没有尾部斜杠）

### 步骤 4: 查看详细错误信息

在浏览器开发者工具中：
1. 打开 **Network** 标签
2. 找到失败的请求（`/api/chat`）
3. 点击查看 **Response** 标签
4. 查看错误详情

## 📝 检查清单

- [ ] 后端服务正在运行（Railway 显示 "Active"）
- [ ] 可以访问后端 `/health` 端点
- [ ] Vercel 环境变量已正确配置
- [ ] `VALUE_CANVAS_API_URL_PRODUCTION` 没有尾部斜杠
- [ ] 后端已重新部署（包含 CORS 配置）
- [ ] Vercel 已重新部署（环境变量生效）

## 🆘 如果问题仍然存在

1. **查看 Railway 日志**：检查后端是否有错误
2. **查看 Vercel 函数日志**：检查前端 API 路由的错误
3. **测试后端直接调用**：使用 curl 或 Postman 测试后端 API
4. **检查网络连接**：确认 Railway 和 Vercel 之间的网络连接正常

