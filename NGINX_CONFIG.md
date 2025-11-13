# Nginx 反向代理配置指南

## 问题说明

下载大音频文件或转换格式时，默认的 Nginx 超时设置会导致 **504 Gateway Timeout** 错误。

**原因**：
- 大文件下载需要较长时间
- M4A 转 MP3 格式转换需要额外处理时间
- Nginx 默认 `proxy_read_timeout` 只有 60 秒

## 配置示例

### 子路径部署（例如: `/podcast`）

```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    location /podcast {
        rewrite ^/podcast/(.*)$ /$1 break;
        proxy_pass http://127.0.0.1:5000;
        
        # 基础代理头
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Script-Name /podcast;
        
        # ⚠️ 关键超时配置（解决 504 错误）
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 1800s;        # 最重要！30分钟
        
        # 流式传输配置
        proxy_buffering off;
        proxy_request_buffering off;
        
        # 客户端配置
        client_max_body_size 100M;
        client_body_timeout 300s;
        send_timeout 1800s;              # 30分钟
        
        # HTTP 1.1 支持
        proxy_http_version 1.1;
        proxy_set_header Connection "";
    }
}
```

### 根路径部署（例如: `/`）

```nginx
location / {
    proxy_pass http://127.0.0.1:5000;
    
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    
    # 超时配置
    proxy_connect_timeout 300s;
    proxy_send_timeout 300s;
    proxy_read_timeout 1800s;
    
    # 流式传输
    proxy_buffering off;
    proxy_request_buffering off;
    
    # 客户端配置
    client_max_body_size 100M;
    client_body_timeout 300s;
    send_timeout 1800s;
    
    proxy_http_version 1.1;
    proxy_set_header Connection "";
}
```

## 关键参数说明

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| `proxy_read_timeout` | **1800s** | **最重要！** 处理大文件和转换需要30分钟 |
| `send_timeout` | **1800s** | 向客户端传输大文件需要30分钟 |
| `proxy_connect_timeout` | 300s | 连接后端超时（5分钟） |
| `proxy_buffering` | **off** | 关闭缓冲，启用流式传输，实时显示进度 |
| `client_max_body_size` | 100M | 支持上传 OPML 等文件 |

**为什么需要 30 分钟超时？**
- 100MB 音频文件 + 格式转换 ≈ 5-10 分钟
- 慢速网络用户可能需要更长时间
- 默认 60 秒会导致下载失败

## 应用配置

```bash
# 测试配置
sudo nginx -t

# 重新加载
sudo nginx -s reload
```

## 故障排查

### 仍然出现 504 错误？

```bash
# 1. 确认配置已加载
sudo nginx -T | grep proxy_read_timeout

# 2. 查看后端日志
tail -f app.log

# 3. 检查 Flask 应用
curl http://localhost:5000/
```

### 下载中断？

可能原因：
- 客户端网络不稳定
- 源服务器限速或超时
- 磁盘空间不足

```bash
# 查看磁盘空间
df -h

# 查看应用日志
grep "下载请求" app.log | tail -20
```

## 总结

**最关键的三个配置：**
1. ✅ `proxy_read_timeout 1800s` - 最重要！
2. ✅ `send_timeout 1800s` - 向客户端传输
3. ✅ `proxy_buffering off` - 启用流式传输

配置完成后重启 Nginx 即可解决 504 超时问题。
