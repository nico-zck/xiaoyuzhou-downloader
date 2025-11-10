# Docker 部署指南

## 推荐方案：GitHub Actions自动构建（Windows用户首选）

### 为什么推荐GitHub Actions？

- ✅ **无需本地构建**：在GitHub的Linux服务器上自动构建
- ✅ **多平台支持**：自动构建amd64和arm64版本
- ✅ **完全免费**：GitHub Actions对公开仓库免费
- ✅ **自动化**：代码推送后自动构建和发布
- ✅ **适合Windows**：不需要在Windows上安装Docker

### 快速设置

1. **添加GitHub Secrets**（在仓库Settings → Secrets → Actions）：
   - `DOCKER_USERNAME`: 你的Docker Hub用户名
   - `DOCKER_PASSWORD`: Docker Hub访问令牌（不是密码）

2. **创建Docker Hub访问令牌**：
   - 访问 https://hub.docker.com/settings/security
   - 点击 "New Access Token"
   - 权限选择 "Read, Write, Delete"
   - 复制生成的令牌

3. **推送代码**：
   ```bash
   git add .
   git commit -m "Add Docker support"
   git push origin main
   ```

4. **查看构建**：
   - 在GitHub仓库的 Actions 标签页查看
   - 构建完成后，镜像会自动推送到Docker Hub

### 使用已构建的镜像

构建完成后，其他人可以直接使用：

```bash
docker run -d -p 5000:5000 \
  -v $(pwd)/downloads:/app/downloads \
  -v $(pwd)/users:/app/users \
  -v $(pwd)/uploads:/app/uploads \
  -v $(pwd)/logs:/app/logs \
  your-username/podcast-downloader:latest
```

## 本地构建Docker镜像（可选）

### 方法1：使用Docker命令

```bash
# 构建镜像
docker build -t podcast-downloader:latest .

# 运行容器
docker run -d \
  --name podcast-downloader \
  -p 5000:5000 \
  -v $(pwd)/downloads:/app/downloads \
  -v $(pwd)/users:/app/users \
  -v $(pwd)/uploads:/app/uploads \
  -v $(pwd)/logs:/app/logs \
  podcast-downloader:latest
```

### 方法2：使用Docker Compose（推荐）

```bash
# 构建并启动
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

## 访问应用

启动后，在浏览器中访问：`http://localhost:5000`

## 数据持久化

使用Docker Compose时，以下目录会自动挂载到宿主机：
- `./downloads` - 下载的音频文件
- `./users` - 用户数据
- `./uploads` - 上传的文件
- `./logs` - 日志文件

## 发布Docker镜像

### 1. 登录Docker Hub

```bash
docker login
```

### 2. 标记镜像

```bash
# 格式：docker tag <本地镜像名> <Docker Hub用户名>/<镜像名>:<标签>
docker tag podcast-downloader:latest your-username/podcast-downloader:latest
docker tag podcast-downloader:latest your-username/podcast-downloader:v1.0.0
```

### 3. 推送镜像

```bash
# 推送latest标签
docker push your-username/podcast-downloader:latest

# 推送版本标签
docker push your-username/podcast-downloader:v1.0.0
```

### 4. 使用已发布的镜像

其他人可以使用以下命令运行：

```bash
docker run -d \
  --name podcast-downloader \
  -p 5000:5000 \
  -v $(pwd)/downloads:/app/downloads \
  -v $(pwd)/users:/app/users \
  -v $(pwd)/uploads:/app/uploads \
  -v $(pwd)/logs:/app/logs \
  your-username/podcast-downloader:latest
```

或使用docker-compose.yml（需要修改镜像名称）：

```yaml
services:
  podcast-downloader:
    image: your-username/podcast-downloader:latest
    # ... 其他配置
```

## 其他Docker镜像仓库

### GitHub Container Registry (ghcr.io)

```bash
# 登录
echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin

# 标记
docker tag podcast-downloader:latest ghcr.io/your-username/podcast-downloader:latest

# 推送
docker push ghcr.io/your-username/podcast-downloader:latest
```

### 阿里云容器镜像服务

```bash
# 登录
docker login --username=your-username registry.cn-hangzhou.aliyuncs.com

# 标记
docker tag podcast-downloader:latest registry.cn-hangzhou.aliyuncs.com/namespace/podcast-downloader:latest

# 推送
docker push registry.cn-hangzhou.aliyuncs.com/namespace/podcast-downloader:latest
```

## 多平台构建（可选）

如果需要支持ARM架构（如树莓派、NAS等）：

```bash
# 安装buildx
docker buildx create --use

# 构建多平台镜像
docker buildx build --platform linux/amd64,linux/arm64 \
  -t your-username/podcast-downloader:latest \
  --push .
```

## 注意事项

1. **端口映射**：确保5000端口未被占用，或修改为其他端口
2. **数据备份**：定期备份 `downloads` 和 `users` 目录
3. **资源限制**：可以在docker-compose.yml中添加资源限制：

```yaml
services:
  podcast-downloader:
    # ...
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
```

