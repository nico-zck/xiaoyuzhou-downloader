# GitHub Actions 自动构建设置指南

## 为什么使用GitHub Actions？

对于Windows用户，使用GitHub Actions构建Docker镜像有以下优势：

1. **无需本地环境**：不需要在Windows上安装Docker Desktop
2. **Linux环境构建**：在GitHub的Linux服务器上构建，确保兼容性
3. **多平台支持**：自动构建amd64和arm64版本
4. **完全自动化**：代码推送后自动构建和发布
5. **完全免费**：公开仓库的GitHub Actions完全免费

## 设置步骤

### 步骤1：创建Docker Hub访问令牌

1. 访问 https://hub.docker.com
2. 登录你的账户
3. 进入 Settings → Security
4. 点击 "New Access Token"
5. 填写描述（如：GitHub Actions）
6. 权限选择 "Read, Write, Delete"
7. 点击 "Generate"
8. **重要**：复制生成的令牌（只显示一次，请保存好）

### 步骤2：在GitHub仓库中添加Secrets

1. 打开你的GitHub仓库
2. 点击 Settings → Secrets and variables → Actions
3. 点击 "New repository secret"
4. 添加以下两个Secrets：

   **Secret 1:**
   - Name: `DOCKER_USERNAME`
   - Value: 你的Docker Hub用户名

   **Secret 2:**
   - Name: `DOCKER_PASSWORD`
   - Value: 步骤1中创建的访问令牌（不是Docker Hub密码）

### 步骤3：修改工作流文件（可选）

如果你使用不同的Docker Hub用户名，需要修改 `.github/workflows/docker-build-simple.yml`：

```yaml
env:
  IMAGE_NAME: ${{ secrets.DOCKER_USERNAME || 'your-username' }}/podcast-downloader
```

将 `your-username` 替换为你的默认用户名（如果未设置Secret）。

### 步骤4：推送代码

```bash
git add .
git commit -m "Add GitHub Actions for Docker build"
git push origin main
```

### 步骤5：查看构建状态

1. 在GitHub仓库页面，点击 "Actions" 标签
2. 选择 "Build and Push Docker Image" 工作流
3. 查看构建进度和日志

### 步骤6：验证镜像

构建完成后，在Docker Hub查看你的镜像：
```
https://hub.docker.com/r/your-username/podcast-downloader
```

## 手动触发构建

如果需要手动触发构建：

1. 在GitHub仓库页面，点击 "Actions" 标签
2. 选择 "Build and Push Docker Image" 工作流
3. 点击 "Run workflow"
4. 选择分支，点击 "Run workflow"

## 使用标签发布版本

当你创建Git标签时，会自动构建并发布版本：

```bash
git tag v1.0.0
git push origin v1.0.0
```

这会在Docker Hub创建 `v1.0.0` 标签的镜像。

## 故障排除

### 构建失败：认证错误

- 检查 `DOCKER_USERNAME` 和 `DOCKER_PASSWORD` 是否正确
- 确保使用的是访问令牌，不是密码
- 确保令牌权限包含 "Write"

### 构建失败：找不到Dockerfile

- 确保 `Dockerfile` 在仓库根目录
- 检查 `.dockerignore` 是否正确

### 推送失败：权限不足

- 检查Docker Hub访问令牌权限
- 确保令牌未过期

## 高级配置

### 只构建特定分支

修改 `.github/workflows/docker-build-simple.yml`：

```yaml
on:
  push:
    branches:
      - main  # 只构建main分支
```

### 添加更多平台

修改构建步骤：

```yaml
platforms: linux/amd64,linux/arm64,linux/arm/v7
```

### 添加构建缓存

工作流文件已包含缓存配置，可以加速后续构建。

## 其他CI/CD选项

如果你不想使用GitHub Actions，也可以考虑：

1. **GitLab CI/CD** - 类似GitHub Actions
2. **Jenkins** - 需要自己的服务器
3. **CircleCI** - 有免费额度
4. **Travis CI** - 有免费额度

