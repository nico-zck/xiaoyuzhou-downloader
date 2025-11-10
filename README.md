# 小宇宙播客下载器

一个基于RSS订阅监测小宇宙播客平台节目更新并自动下载音频文件的Web应用。

## 功能特性

1. **单集节目下载**：根据小宇宙单集节目链接，自动转换并提供下载链接
2. **OPML订阅管理**：支持上传OPML文件，管理多个播客订阅
3. **自动下载**：支持下载最新N集节目或监听新节目自动下载
4. **任务管理**：实时查看下载任务状态，支持取消任务
5. **内容管理**：管理已下载的文件，支持手动删除
6. **用户管理**：支持多用户，每个用户可以管理自己的订阅和下载任务

## 安装

### 方式1：Docker部署（推荐，适合NAS）

```bash
# 使用Docker Compose
docker-compose up -d

# 或使用Docker命令
docker build -t podcast-downloader:latest .
docker run -d -p 5000:5000 \
  -v $(pwd)/downloads:/app/downloads \
  -v $(pwd)/users:/app/users \
  -v $(pwd)/uploads:/app/uploads \
  podcast-downloader:latest
```

详细说明请参考 [DOCKER.md](DOCKER.md)

### 方式2：本地安装

#### 1. 安装Python依赖

```bash
pip install -r requirements.txt
```

#### 2. 安装ffmpeg

**Windows:**
- 下载ffmpeg: https://ffmpeg.org/download.html
- 解压并添加到系统PATH环境变量

**Linux:**
```bash
sudo apt update && sudo apt install ffmpeg
```

**Mac:**
```bash
brew install ffmpeg
```

#### 3. 运行应用

**Windows:**
```bash
python app.py
```
或双击 `run.bat`

**Linux/Mac:**
```bash
python3 app.py
```
或运行 `chmod +x run.sh && ./run.sh`

### 3. 访问应用

在浏览器中访问 `http://localhost:5000`

## 使用说明

### 单集下载

1. 在"单集下载"页面输入小宇宙单集链接（例如：`https://www.xiaoyuzhoufm.com/episode/690ca389af4fc00da77838c5`）
2. 点击"获取信息"按钮
3. 查看节目信息（封面、标题、描述）
4. 点击"下载音频"按钮获取下载链接

### 订阅管理

1. **创建用户**
   - 在"订阅管理"页面输入用户名
   - 点击"创建/加载用户"按钮
   - 也可以点击"查看已有用户"选择已有用户

2. **上传OPML文件**
   - 点击"选择文件"选择OPML文件
   - 点击"上传OPML"按钮
   - 系统会自动解析订阅列表

3. **查看订阅节目**
   - 在订阅列表中点击"查看节目"按钮
   - 可以查看每个订阅的节目列表
   - 每个节目显示封面、标题、描述和下载链接

4. **下载选项**
   - **下载最新N集**：输入要下载的集数，点击"开始下载"
   - **启动监听任务**：自动检测新节目并下载（每分钟检查一次）

### 任务管理

- 查看所有下载和监听任务的状态
- 实时显示任务进度
- 可以取消正在运行的任务

### 下载管理

- 查看所有已下载的文件
- 显示文件信息（标题、大小、下载时间）
- 可以下载或删除文件

## 技术说明

### 小宇宙音频获取

程序会尝试多种方法获取小宇宙播客的音频下载链接：
1. 从页面JavaScript中提取音频URL
2. 通过小宇宙API获取音频信息
3. 支持多种音频格式（mp3, m4a, aac等）

### RSS订阅解析

- 支持标准RSS格式
- 支持HTML页面中的RSS链接自动发现
- 自动处理相对URL转换为绝对URL

### OPML文件格式

OPML文件应包含以下格式：
```xml
<outline title="播客名称" 
         text="描述" 
         xmlUrl="RSS链接" 
         type="rss"/>
```

## 注意事项

1. 首次运行会自动创建必要的文件夹（uploads, downloads, users）
2. 下载的文件保存在 `downloads` 文件夹
3. 用户数据保存在 `users` 文件夹
4. 监听任务会在后台持续运行，每分钟检查一次更新
5. **临时文件管理**：
   - 普通下载使用流式传输，**不会创建临时文件**，数据直接从源服务器传输到客户端
   - 只有在选择"转换为mp3"时才会创建临时文件，转换完成后**会自动删除**临时文件
   - 无需担心临时文件积累问题
6. **音频格式转换**：
   - 支持将m4a格式转换为mp3格式
   - 需要安装ffmpeg（请参考下方说明）
   - 可以在下载时选择自动转换，也可以在下载管理页面手动转换已下载的m4a文件

## Docker镜像发布

### 推荐方案：使用GitHub Actions自动构建（适合Windows用户）

**优点：**
- ✅ 无需本地构建，自动在Linux环境构建
- ✅ 支持多平台（amd64/arm64）
- ✅ 代码推送后自动构建和发布
- ✅ 完全免费

**设置步骤：**

1. **在GitHub仓库中添加Secrets：**
   - 进入仓库 Settings → Secrets and variables → Actions
   - 添加 `DOCKER_USERNAME`（你的Docker Hub用户名）
   - 添加 `DOCKER_PASSWORD`（你的Docker Hub访问令牌，不是密码）

2. **创建Docker Hub访问令牌：**
   - 访问 https://hub.docker.com/settings/security
   - 点击 "New Access Token"
   - 创建令牌并复制（只显示一次）

3. **推送代码到GitHub：**
   ```bash
   git add .
   git commit -m "Add Docker support"
   git push origin main
   ```

4. **查看构建状态：**
   - 在GitHub仓库的 Actions 标签页查看构建进度
   - 构建完成后，镜像会自动推送到Docker Hub

### 方案2：本地构建（Windows）

如果你有Docker Desktop，也可以本地构建：

```bash
# 1. 登录Docker Hub
docker login

# 2. 构建并标记镜像
docker build -t your-username/podcast-downloader:latest .

# 3. 推送镜像
docker push your-username/podcast-downloader:latest
```

**注意：** Windows上构建的镜像可能只支持amd64平台，如果需要支持ARM架构（如树莓派、某些NAS），建议使用GitHub Actions。

### 方案3：使用Docker Hub自动构建

1. 在Docker Hub创建仓库
2. 连接GitHub仓库
3. 设置自动构建规则
4. 每次推送代码时自动构建

详细说明请参考 [DOCKER.md](DOCKER.md)

## 音频格式转换

### 安装ffmpeg（仅本地安装需要）

**Windows:**
1. 下载ffmpeg: https://ffmpeg.org/download.html
2. 解压并添加到系统PATH环境变量
3. 或在项目目录中放置ffmpeg.exe

**Linux:**
```bash
sudo apt update
sudo apt install ffmpeg
```

**Mac:**
```bash
brew install ffmpeg
```

### 使用方法

1. **下载时转换**：在单集下载页面，勾选"如果是m4a格式，自动转换为mp3"选项
2. **已下载文件转换**：在下载管理页面，点击m4a文件旁边的"转换为MP3"按钮

转换后的mp3文件会保留原始文件的元数据信息。

## 故障排除

1. **无法获取音频链接**：小宇宙可能更新了API，需要更新解析逻辑
2. **RSS解析失败**：某些非标准RSS源可能需要手动处理
3. **下载失败**：检查网络连接和文件URL是否有效
4. **转换失败**：检查ffmpeg是否已正确安装并在PATH中可用

## 许可证

MIT License

