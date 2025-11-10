let currentUsername = '';

// 获取应用根路径（支持反向代理）
const APPLICATION_ROOT = window.APPLICATION_ROOT || '';

// API请求辅助函数
function apiUrl(path) {
    // 确保path以/开头
    if (!path.startsWith('/')) {
        path = '/' + path;
    }
    return APPLICATION_ROOT + path;
}

// 页面导航
document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const page = btn.dataset.page;
        switchPage(page);
        document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
    });
});

function switchPage(pageName) {
    document.querySelectorAll('.page').forEach(page => {
        page.classList.remove('active');
    });
    document.getElementById(`${pageName}-page`).classList.add('active');
    
    // 加载对应页面的数据
    if (pageName === 'tasks') {
        loadTasks();
    } else if (pageName === 'downloads') {
        loadDownloads();
    }
}

// 单集下载功能
async function getEpisodeInfo() {
    const url = document.getElementById('episode-url').value.trim();
    if (!url) {
        alert('请输入小宇宙单集链接');
        return;
    }
    
    const infoDiv = document.getElementById('episode-info');
    infoDiv.style.display = 'none';
    
    try {
        const response = await fetch(apiUrl('/api/episode/info'), {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ url })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            document.getElementById('episode-title').textContent = data.title || '未知标题';
            document.getElementById('episode-description').textContent = data.description || '暂无描述';
            document.getElementById('episode-cover').src = data.cover || '/static/default-cover.png';
            document.getElementById('episode-cover').onerror = function() {
                this.src = 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200"><rect width="200" height="200" fill="%23ddd"/><text x="50%25" y="50%25" text-anchor="middle" dy=".3em" fill="%23999">无封面</text></svg>';
            };
            infoDiv.style.display = 'block';
            infoDiv.dataset.url = url;
        } else {
            alert('获取节目信息失败: ' + (data.error || '未知错误'));
        }
    } catch (error) {
        alert('请求失败: ' + error.message);
    }
}

async function downloadEpisode() {
    const url = document.getElementById('episode-info').dataset.url;
    if (!url) return;
    
    const downloadBtn = document.querySelector('#episode-info .download-btn');
    const originalText = downloadBtn.textContent;
    downloadBtn.textContent = '获取下载链接中...';
    downloadBtn.disabled = true;
    
    try {
        // 首先获取下载链接和节目标题
        const response = await fetch(apiUrl('/api/episode/download-url'), {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ url })
        });
        
        const data = await response.json();
        
        if (response.ok && data.download_url) {
            // 获取节目标题
            const title = document.getElementById('episode-title').textContent || 'episode';
            const safeTitle = title.replace(/[<>:"/\\|?*]/g, '_').trim();
            
            // 通过API下载，设置正确的文件名
            downloadBtn.textContent = '下载中...';
            
            // 检查是否要转换
            const convertToMp3 = document.getElementById('convert-to-mp3').checked;
            
            const downloadResponse = await fetch(apiUrl('/api/episode/download'), {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    url: data.download_url,
                    filename: safeTitle,
                    convert_to_mp3: convertToMp3
                })
            });
            
            if (downloadResponse.ok) {
                const blob = await downloadResponse.blob();
                const blobUrl = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = blobUrl;
                
                // 从Content-Disposition header获取文件名
                const contentDisposition = downloadResponse.headers.get('Content-Disposition');
                let filename = `${safeTitle}.mp3`;
                
                if (contentDisposition) {
                    // 尝试解析 filename*=UTF-8''encoded_filename 格式（RFC 5987）
                    const utf8Match = contentDisposition.match(/filename\*=UTF-8''([^;]+)/);
                    if (utf8Match) {
                        try {
                            filename = decodeURIComponent(utf8Match[1]);
                        } catch (e) {
                            // 如果解码失败，尝试普通格式
                            const normalMatch = contentDisposition.match(/filename="?([^";]+)"?/);
                            if (normalMatch) {
                                filename = normalMatch[1];
                            }
                        }
                    } else {
                        // 尝试普通格式
                        const normalMatch = contentDisposition.match(/filename="?([^";]+)"?/);
                        if (normalMatch) {
                            filename = normalMatch[1].replace(/['"]/g, '');
                        }
                    }
                }
                
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(blobUrl);
                
                downloadBtn.textContent = '下载完成';
                setTimeout(() => {
                    downloadBtn.textContent = originalText;
                    downloadBtn.disabled = false;
                }, 2000);
            } else {
                const errorData = await downloadResponse.json();
                alert('下载失败: ' + (errorData.error || '未知错误'));
                downloadBtn.textContent = originalText;
                downloadBtn.disabled = false;
            }
        } else {
            alert('获取下载链接失败: ' + (data.error || '未知错误'));
            downloadBtn.textContent = originalText;
            downloadBtn.disabled = false;
        }
    } catch (error) {
        alert('请求失败: ' + error.message);
        downloadBtn.textContent = originalText;
        downloadBtn.disabled = false;
    }
}

// 用户管理
async function createUser() {
    const username = document.getElementById('username').value.trim();
    if (!username) {
        alert('请输入用户名');
        return;
    }
    
    try {
        const response = await fetch(apiUrl('/api/user/create'), {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ username })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            currentUsername = username;
            document.getElementById('user-status').innerHTML = 
                `<div class="status-message success">${data.message}: ${username}</div>`;
            document.getElementById('opml-section').style.display = 'block';
            document.getElementById('download-options').style.display = 'block';
            loadSubscriptions();
        } else {
            document.getElementById('user-status').innerHTML = 
                `<div class="status-message error">${data.error || '创建失败'}</div>`;
        }
    } catch (error) {
        document.getElementById('user-status').innerHTML = 
            `<div class="status-message error">请求失败: ${error.message}</div>`;
    }
}

// 加载用户列表
async function loadUsers() {
    try {
        const response = await fetch(apiUrl('/api/users'));
        const data = await response.json();
        
        if (response.ok) {
            const listDiv = document.getElementById('users-list');
            if (data.users.length === 0) {
                listDiv.innerHTML = '<p>暂无用户</p>';
            } else {
                listDiv.innerHTML = `
                    <h4>已有用户：</h4>
                    ${data.users.map(user => `
                        <div class="subscription-item" style="cursor: pointer;" onclick="selectUser('${user.username}')">
                            <h4>${user.username}</h4>
                            <p>创建时间: ${new Date(user.created_at).toLocaleString('zh-CN')} | 订阅数: ${user.subscriptions_count}</p>
                        </div>
                    `).join('')}
                `;
            }
        }
    } catch (error) {
        console.error('加载用户列表失败:', error);
    }
}

// 选择用户
function selectUser(username) {
    document.getElementById('username').value = username;
    createUser();
}

// OPML上传
async function uploadOPML() {
    const fileInput = document.getElementById('opml-file');
    const file = fileInput.files[0];
    
    if (!file) {
        alert('请选择OPML文件');
        return;
    }
    
    if (!currentUsername) {
        alert('请先创建用户');
        return;
    }
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        const response = await fetch(apiUrl(`/api/user/${currentUsername}/opml`), {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (response.ok) {
            document.getElementById('opml-status').innerHTML = 
                `<div class="status-message success">OPML文件解析成功，共 ${data.subscriptions.length} 个订阅</div>`;
            loadSubscriptions();
        } else {
            document.getElementById('opml-status').innerHTML = 
                `<div class="status-message error">${data.error || '上传失败'}</div>`;
        }
    } catch (error) {
        document.getElementById('opml-status').innerHTML = 
            `<div class="status-message error">请求失败: ${error.message}</div>`;
    }
}

// 加载订阅列表
async function loadSubscriptions() {
    if (!currentUsername) return;
    
    try {
        const response = await fetch(apiUrl(`/api/user/${currentUsername}/subscriptions`));
        const data = await response.json();
        
        if (response.ok) {
            const listDiv = document.getElementById('subscriptions-list');
            if (data.subscriptions.length === 0) {
                listDiv.innerHTML = '<p>暂无订阅，请上传OPML文件</p>';
            } else {
                listDiv.innerHTML = data.subscriptions.map((sub, index) => `
                    <div class="subscription-item">
                        <h4>${sub.title}</h4>
                        <p>${sub.text || ''}</p>
                        <button onclick="loadEpisodes(${index})">查看节目</button>
                    </div>
                `).join('');
            }
            document.getElementById('subscriptions-section').style.display = 'block';
        }
    } catch (error) {
        console.error('加载订阅失败:', error);
    }
}

// 加载节目列表
async function loadEpisodes(subIndex) {
    if (!currentUsername) return;
    
    const listDiv = document.getElementById('subscriptions-list');
    // 显示加载状态
    listDiv.innerHTML = `
        <div style="text-align: center; padding: 40px;">
            <div class="loading" style="width: 40px; height: 40px; border-width: 4px; margin: 0 auto 20px;"></div>
            <p>正在加载节目列表，请稍候...</p>
        </div>
    `;
    
    try {
        const response = await fetch(apiUrl(`/api/user/${currentUsername}/subscriptions/${subIndex}/episodes`));
        const data = await response.json();
        
        if (response.ok) {
            const episodesHtml = data.episodes.map((episode, idx) => {
                // 清理文件名，移除非法字符并转义单引号
                const safeTitle = (episode.title || '未知标题').replace(/[<>:"/\\|?*]/g, '_').trim().replace(/'/g, "\\'");
                const safeAudioUrl = (episode.audio_url || '').replace(/'/g, "\\'");
                return `
                    <div class="episode-item">
                        <img src="${episode.cover || 'data:image/svg+xml,<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"80\" height=\"80\"><rect width=\"80\" height=\"80\" fill=\"%23ddd\"/></svg>'}" 
                             alt="封面" onerror="this.src='data:image/svg+xml,<svg xmlns=\\'http://www.w3.org/2000/svg\\' width=\\'80\\' height=\\'80\\'><rect width=\\'80\\' height=\\'80\\' fill=\\'%23ddd\\'/></svg>'">
                        <div class="episode-item-content">
                            <h5>${episode.title}</h5>
                            <p>${episode.description || ''}</p>
                            ${episode.audio_url ? `
                                <button onclick="downloadEpisodeFile('${safeAudioUrl}', '${safeTitle}', ${idx})" 
                                        class="download-btn" style="padding: 8px 16px; font-size: 14px;">
                                    下载
                                </button>
                            ` : '<span style="color: #999;">暂无下载链接</span>'}
                        </div>
                    </div>
                `;
            }).join('');
            
            listDiv.innerHTML = `
                <button onclick="loadSubscriptions()" style="margin-bottom: 15px;">← 返回订阅列表</button>
                <h4>${data.subscription.title} - 节目列表</h4>
                ${episodesHtml}
            `;
        } else {
            listDiv.innerHTML = `
                <div class="status-message error">加载失败: ${data.error || '未知错误'}</div>
                <button onclick="loadSubscriptions()" style="margin-top: 15px;">← 返回订阅列表</button>
            `;
        }
    } catch (error) {
        listDiv.innerHTML = `
            <div class="status-message error">加载失败: ${error.message}</div>
            <button onclick="loadSubscriptions()" style="margin-top: 15px;">← 返回订阅列表</button>
        `;
    }
}

// 下载节目文件（使用正确的文件名）
async function downloadEpisodeFile(audioUrl, title, index) {
    if (!audioUrl) {
        alert('没有可用的下载链接');
        return;
    }
    
    try {
        // 显示下载中状态
        const buttons = document.querySelectorAll('.episode-item button');
        if (buttons[index]) {
            const originalText = buttons[index].textContent;
            buttons[index].textContent = '下载中...';
            buttons[index].disabled = true;
            
            // 通过服务器下载，设置正确的文件名
            const response = await fetch(apiUrl('/api/episode/download'), {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    url: audioUrl,
                    filename: title
                })
            });
            
            if (response.ok) {
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `${title}.mp3`; // 设置文件名
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(url);
                
                buttons[index].textContent = '下载完成';
                setTimeout(() => {
                    buttons[index].textContent = originalText;
                    buttons[index].disabled = false;
                }, 2000);
            } else {
                const data = await response.json();
                alert('下载失败: ' + (data.error || '未知错误'));
                buttons[index].textContent = originalText;
                buttons[index].disabled = false;
            }
        }
    } catch (error) {
        alert('下载失败: ' + error.message);
        const buttons = document.querySelectorAll('.episode-item button');
        if (buttons[index]) {
            buttons[index].disabled = false;
        }
    }
}

// 下载最新N集
async function downloadLatest() {
    if (!currentUsername) {
        alert('请先创建用户');
        return;
    }
    
    const count = parseInt(document.getElementById('latest-count').value) || 5;
    
    try {
        const response = await fetch(apiUrl(`/api/user/${currentUsername}/download/latest`), {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ count })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            alert('下载任务已创建，请到任务管理页面查看进度');
            switchPage('tasks');
            loadTasks();
        } else {
            alert('创建下载任务失败: ' + (data.error || '未知错误'));
        }
    } catch (error) {
        alert('请求失败: ' + error.message);
    }
}

// 启动监听任务
async function startMonitor() {
    if (!currentUsername) {
        alert('请先创建用户');
        return;
    }
    
    if (!confirm('确定要启动监听任务吗？这将自动下载所有新发布的节目。')) {
        return;
    }
    
    try {
        const response = await fetch(apiUrl(`/api/user/${currentUsername}/monitor/start`), {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            alert('监听任务已启动，请到任务管理页面查看');
            switchPage('tasks');
            loadTasks();
        } else {
            alert('启动监听任务失败: ' + (data.error || '未知错误'));
        }
    } catch (error) {
        alert('请求失败: ' + error.message);
    }
}

// 加载任务列表
async function loadTasks() {
    try {
        const response = await fetch(apiUrl('/api/tasks'));
        const data = await response.json();
        
        if (response.ok) {
            const listDiv = document.getElementById('tasks-list');
            if (data.tasks.length === 0) {
                listDiv.innerHTML = '<p>暂无任务</p>';
            } else {
                listDiv.innerHTML = data.tasks.map(task => {
                    const progress = task.progress || {};
                    const progressPercent = progress.total > 0 
                        ? Math.round((progress.completed / progress.total) * 100) 
                        : 0;
                    
                    return `
                        <div class="task-item ${task.status}">
                            <div class="task-header">
                                <h4>${task.type === 'download_latest' ? '下载最新节目' : '监听任务'} - ${task.username}</h4>
                                <span class="task-status ${task.status}">${getStatusText(task.status)}</span>
                            </div>
                            <p>创建时间: ${new Date(task.created_at).toLocaleString('zh-CN')}</p>
                            ${task.type === 'download_latest' ? `
                                <div class="task-progress">
                                    <p>进度: ${progress.completed}/${progress.total} (成功: ${progress.completed - (progress.failed || 0)}, 失败: ${progress.failed || 0})</p>
                                    <div class="progress-bar">
                                        <div class="progress-fill" style="width: ${progressPercent}%"></div>
                                    </div>
                                </div>
                            ` : `
                                <p>已下载: ${task.downloaded_count || 0} 集</p>
                                <p>最后检查: ${new Date(task.last_check).toLocaleString('zh-CN')}</p>
                            `}
                            ${task.status === 'running' || task.status === 'pending' ? 
                                `<button onclick="cancelTask('${task.task_id}')" class="delete-btn">取消任务</button>` : ''
                            }
                        </div>
                    `;
                }).join('');
            }
        }
    } catch (error) {
        console.error('加载任务失败:', error);
    }
}

function getStatusText(status) {
    const statusMap = {
        'pending': '等待中',
        'running': '运行中',
        'completed': '已完成',
        'failed': '失败',
        'cancelled': '已取消'
    };
    return statusMap[status] || status;
}

// 取消任务
async function cancelTask(taskId) {
    if (!confirm('确定要取消这个任务吗？')) {
        return;
    }
    
    try {
        const response = await fetch(apiUrl(`/api/tasks/${taskId}/cancel`), {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            loadTasks();
        } else {
            alert('取消任务失败: ' + (data.error || '未知错误'));
        }
    } catch (error) {
        alert('请求失败: ' + error.message);
    }
}

// 加载下载列表
async function loadDownloads() {
    try {
        const response = await fetch(apiUrl('/api/downloads'));
        const data = await response.json();
        
        if (response.ok) {
            const listDiv = document.getElementById('downloads-list');
            if (data.downloads.length === 0) {
                listDiv.innerHTML = '<p>暂无下载文件</p>';
            } else {
                listDiv.innerHTML = data.downloads.map(download => {
                    const size = (download.size / 1024 / 1024).toFixed(2);
                    const episodeInfo = download.episode_info || {};
                    const fileExt = download.filename.split('.').pop().toLowerCase();
                    const isM4A = fileExt === 'm4a';
                    return `
                        <div class="download-item">
                            <div class="download-item-info">
                                <h5>${episodeInfo.title || download.filename}</h5>
                                <p>${episodeInfo.description || ''}</p>
                                <p style="font-size: 12px; color: #999;">
                                    大小: ${size} MB | 格式: ${fileExt.toUpperCase()} | 下载时间: ${new Date(download.downloaded_at).toLocaleString('zh-CN')}
                                </p>
                            </div>
                            <div>
                                <a href="${apiUrl('/downloads/' + download.file_id)}" download class="download-btn" style="display: inline-block; text-decoration: none; margin-right: 10px;">下载</a>
                                ${isM4A ? `<button onclick="convertToMp3('${download.file_id}')" class="monitor-btn" style="margin-right: 10px;">转换为MP3</button>` : ''}
                                <button onclick="deleteDownload('${download.file_id}')" class="delete-btn">删除</button>
                            </div>
                        </div>
                    `;
                }).join('');
            }
        }
    } catch (error) {
        console.error('加载下载列表失败:', error);
    }
}

// 转换为MP3
async function convertToMp3(fileId) {
    if (!confirm('确定要将此m4a文件转换为mp3格式吗？转换可能需要一些时间。')) {
        return;
    }
    
    try {
        const response = await fetch(apiUrl('/api/audio/convert'), {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ file_id: fileId })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            alert('转换成功！mp3文件已添加到下载列表。');
            loadDownloads();
        } else {
            alert('转换失败: ' + (data.error || '未知错误'));
        }
    } catch (error) {
        alert('请求失败: ' + error.message);
    }
}

// 删除下载文件
async function deleteDownload(fileId) {
    if (!confirm('确定要删除这个文件吗？')) {
        return;
    }
    
    try {
        const response = await fetch(apiUrl(`/api/downloads/${fileId}`), {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            loadDownloads();
        } else {
            alert('删除失败: ' + (data.error || '未知错误'));
        }
    } catch (error) {
        alert('请求失败: ' + error.message);
    }
}

// 定期刷新任务列表
setInterval(() => {
    if (document.getElementById('tasks-page').classList.contains('active')) {
        loadTasks();
    }
}, 5000);

