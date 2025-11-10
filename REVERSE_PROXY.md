# 反向代理配置指南

当你需要通过反向代理（如 Nginx）在子路径（如 `/podcast`）下访问应用时，需要进行以下配置。

## 问题说明

假如直接访问 `http://192.168.2.11:5678/` 正常工作，但通过反向代理访问 `http://192.168.2.11/podcast` 时，静态资源（CSS、JS）会加载失败，因为路径不对：
- ❌ 错误：`http://192.168.2.11/static/style.css`
- ✅ 正确：`http://192.168.2.11/podcast/static/style.css`

## 解决方案

### 1. Docker 配置

在 `docker-compose.yml` 中取消注释并设置环境变量：

```yaml
environment:
  - FLASK_ENV=production
  - LOG_DIR=/app/logs
  - APPLICATION_ROOT=/podcast  # 设置你的路径前缀
  - PROXY_FIX=1                # 启用反向代理支持
```

**重要**: 确保环境变量前面没有 `#` 注释符号！

### 2. Nginx 配置

#### 方法 A: 使用 proxy_pass（推荐）

```nginx
location /podcast {
    # 注意: proxy_pass 后面不要加斜杠
    proxy_pass http://localhost:5000;
    
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    
    # 重要: 告诉Flask应用的路径前缀
    proxy_set_header X-Forwarded-Prefix /podcast;
}
```

#### 方法 B: 使用 rewrite（备选方案）

```nginx
location /podcast {
    rewrite ^/podcast(/.*)?$ $1 break;
    proxy_pass http://localhost:5000;
    
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

### 3. 重启服务

```bash
# 重启 Docker 容器
docker-compose down
docker-compose up -d

# 重启 Nginx
sudo nginx -t          # 测试配置文件
sudo systemctl restart nginx
```

## 验证配置

1. 访问 `http://192.168.2.11/podcast`
2. 打开浏览器开发者工具（F12）-> Network 标签
3. 刷新页面，检查静态资源路径是否正确：
   - ✅ `http://192.168.2.11/podcast/static/style.css`
   - ✅ `http://192.168.2.11/podcast/static/script.js`

## 常见问题

### Q1: 静态资源依然 404

**原因**: 环境变量未生效或 Nginx 配置错误

**解决**:
```bash
# 检查容器环境变量
docker exec podcast-downloader env | grep APPLICATION_ROOT

# 应该输出: APPLICATION_ROOT=/podcast
# 如果没有输出，说明环境变量未设置
```

### Q2: API 请求失败

**原因**: JavaScript 未正确获取 APPLICATION_ROOT

**解决**: 
1. 打开浏览器控制台（F12）-> Console 标签
2. 输入 `window.APPLICATION_ROOT` 查看值
3. 应该输出 `"/podcast"`，如果是 `""`，说明模板未正确渲染

### Q3: 使用其他路径前缀

如果想使用 `/myapp` 而不是 `/podcast`：

1. 修改 `docker-compose.yml`：
   ```yaml
   - APPLICATION_ROOT=/myapp
   ```

2. 修改 Nginx 配置：
   ```nginx
   location /myapp {
       proxy_pass http://localhost:5000;
       proxy_set_header X-Forwarded-Prefix /myapp;
       # ... 其他配置
   }
   ```

## 不使用反向代理

如果直接访问端口（如 `http://localhost:5000`），**不需要**设置这些环境变量：

```yaml
environment:
  - FLASK_ENV=production
  - LOG_DIR=/app/logs
  # 不需要 APPLICATION_ROOT 和 PROXY_FIX
```

## 技术细节

应用使用以下机制支持路径前缀：

1. **后端（Flask）**:
   - 读取 `APPLICATION_ROOT` 环境变量
   - 重写 `url_for()` 函数，自动在所有 URL 前添加前缀
   - `ProxyFix` 中间件处理反向代理的 HTTP 头

2. **前端（JavaScript）**:
   - 从模板注入的 `window.APPLICATION_ROOT` 获取路径前缀
   - `apiUrl()` 函数自动在所有 API 请求前添加前缀

3. **模板（HTML）**:
   - `url_for('static', filename='...')` 自动处理静态资源路径
   - 所有链接自动包含路径前缀

