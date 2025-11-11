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

// 初始化页面导航
function initNavigation() {
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const page = btn.dataset.page;
            switchPage(page);
            document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
        });
    });
}

// 启动任务刷新定时器
function startTaskRefreshTimer() {
    setInterval(() => {
        const tasksPage = document.getElementById('tasks-page');
        if (tasksPage && tasksPage.classList.contains('active')) {
            loadTasks();
        }
    }, 5000);
}

// 统一的初始化函数
function initApp() {
    console.log('初始化应用，APPLICATION_ROOT:', APPLICATION_ROOT);
    initNavigation();
    startTaskRefreshTimer();
}

// 等待DOM加载完成后初始化
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initApp);
} else {
    // DOM已经加载完成
    initApp();
}

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
    
    // 创建状态提示元素
    let statusHint = document.getElementById('download-status-hint');
    if (!statusHint) {
        statusHint = document.createElement('div');
        statusHint.id = 'download-status-hint';
        statusHint.style.marginTop = '10px';
        statusHint.style.fontSize = '14px';
        statusHint.style.color = '#666';
        statusHint.style.fontStyle = 'italic';
        downloadBtn.parentNode.insertBefore(statusHint, downloadBtn.nextSibling);
    }
    
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
            
            // 检查是否要转换
            const convertToMp3 = document.getElementById('convert-to-mp3').checked;
            
            // 根据是否需要转换显示不同的提示
            if (convertToMp3) {
                downloadBtn.textContent = '处理中，请稍候...';
                statusHint.innerHTML = '⚙️ 正在下载原始音频并转换格式，这可能需要一些时间...';
            } else {
                downloadBtn.textContent = '下载中...';
                statusHint.innerHTML = '📥 正在下载音频文件...';
            }
            
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
                // 更新状态提示
                const convertToMp3 = document.getElementById('convert-to-mp3').checked;
                if (convertToMp3) {
                    statusHint.innerHTML = '✅ 格式转换完成，正在下载文件...';
                } else {
                    statusHint.innerHTML = '📥 正在下载文件...';
                }
                
                // 创建进度显示元素
                const progressContainer = document.createElement('div');
                progressContainer.style.marginTop = '10px';
                progressContainer.innerHTML = `
                    <div style="margin-bottom: 5px; font-size: 14px;">
                        <span id="download-progress-text">下载中: 0%</span>
                    </div>
                    <div class="progress-bar">
                        <div id="download-progress-fill" class="progress-fill" style="width: 0%"></div>
                    </div>
                `;
                statusHint.parentNode.insertBefore(progressContainer, statusHint.nextSibling);
                
                // 使用流式下载追踪进度
                const contentLength = downloadResponse.headers.get('Content-Length');
                const total = contentLength ? parseInt(contentLength, 10) : 0;
                let loaded = 0;
                
                const reader = downloadResponse.body.getReader();
                const chunks = [];
                
                while (true) {
                    const { done, value } = await reader.read();
                    
                    if (done) break;
                    
                    chunks.push(value);
                    loaded += value.length;
                    
                    // 更新进度
                    if (total > 0) {
                        const percent = Math.round((loaded / total) * 100);
                        document.getElementById('download-progress-text').textContent = `下载中: ${percent}% (${(loaded / 1024 / 1024).toFixed(2)}MB / ${(total / 1024 / 1024).toFixed(2)}MB)`;
                        document.getElementById('download-progress-fill').style.width = `${percent}%`;
                    } else {
                        document.getElementById('download-progress-text').textContent = `下载中: ${(loaded / 1024 / 1024).toFixed(2)}MB`;
                    }
                }
                
                // 组合所有数据块
                const blob = new Blob(chunks);
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
                
                // 显示完成状态
                document.getElementById('download-progress-text').textContent = '下载完成！';
                document.getElementById('download-progress-fill').style.width = '100%';
                statusHint.innerHTML = '✅ 全部完成！';
                
                setTimeout(() => {
                    progressContainer.remove();
                    if (statusHint && statusHint.parentNode) {
                        statusHint.remove();
                    }
                    downloadBtn.textContent = originalText;
                    downloadBtn.disabled = false;
                }, 2000);
            } else {
                const errorData = await downloadResponse.json();
                alert('下载失败: ' + (errorData.error || '未知错误'));
                if (statusHint && statusHint.parentNode) {
                    statusHint.remove();
                }
                downloadBtn.textContent = originalText;
                downloadBtn.disabled = false;
            }
        } else {
            alert('获取下载链接失败: ' + (data.error || '未知错误'));
            if (statusHint && statusHint.parentNode) {
                statusHint.remove();
            }
            downloadBtn.textContent = originalText;
            downloadBtn.disabled = false;
        }
    } catch (error) {
        alert('请求失败: ' + error.message);
        const statusHint = document.getElementById('download-status-hint');
        if (statusHint && statusHint.parentNode) {
            statusHint.remove();
        }
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
                                <div class="convert-checkbox-container">
                                    <input type="checkbox" id="convert-sub-${idx}" style="width: auto;">
                                    <label for="convert-sub-${idx}">如果是m4a格式，自动转换为mp3</label>
                                </div>
                                <button onclick="downloadEpisodeFile('${safeAudioUrl}', '${safeTitle}', ${idx})" 
                                        class="download-btn" style="padding: 8px 16px; font-size: 14px; margin-top: 8px;">
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
        // 获取转换选项
        const convertCheckbox = document.getElementById(`convert-sub-${index}`);
        const convertToMp3 = convertCheckbox ? convertCheckbox.checked : false;
        
        // 显示下载中状态
        const buttons = document.querySelectorAll('.episode-item button.download-btn');
        if (buttons[index]) {
            const originalText = buttons[index].textContent;
            
            // 创建或获取状态提示元素
            const statusHintId = `status-hint-${index}`;
            let statusHint = document.getElementById(statusHintId);
            
            if (!statusHint) {
                statusHint = document.createElement('div');
                statusHint.id = statusHintId;
                statusHint.style.marginTop = '8px';
                statusHint.style.fontSize = '13px';
                statusHint.style.color = '#666';
                statusHint.style.fontStyle = 'italic';
                buttons[index].parentNode.insertBefore(statusHint, buttons[index].nextSibling);
            }
            
            // 根据是否需要转换显示不同的提示
            if (convertToMp3) {
                buttons[index].textContent = '处理中...';
                statusHint.innerHTML = '⚙️ 正在下载并转换格式，请稍候...';
            } else {
                buttons[index].textContent = '准备下载...';
                statusHint.innerHTML = '📥 正在准备下载...';
            }
            
            buttons[index].disabled = true;
            
            // 通过服务器下载，设置正确的文件名
            const response = await fetch(apiUrl('/api/episode/download'), {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    url: audioUrl,
                    filename: title,
                    convert_to_mp3: convertToMp3
                })
            });
            
            if (response.ok) {
                // 更新状态提示（使用之前已声明的变量）
                if (statusHint) {
                    if (convertToMp3) {
                        statusHint.innerHTML = '✅ 格式转换完成，正在下载...';
                    } else {
                        statusHint.innerHTML = '📥 正在下载文件...';
                    }
                }
                
                // 创建进度显示元素
                const progressId = `progress-${index}`;
                let progressContainer = document.getElementById(progressId);
                
                if (!progressContainer) {
                    progressContainer = document.createElement('div');
                    progressContainer.id = progressId;
                    progressContainer.style.marginTop = '8px';
                    progressContainer.innerHTML = `
                        <div style="margin-bottom: 5px; font-size: 13px; color: #666;">
                            <span id="progress-text-${index}">下载中: 0%</span>
                        </div>
                        <div class="progress-bar">
                            <div id="progress-fill-${index}" class="progress-fill" style="width: 0%"></div>
                        </div>
                    `;
                    const insertAfter = statusHint || buttons[index];
                    insertAfter.parentNode.insertBefore(progressContainer, insertAfter.nextSibling);
                }
                
                // 使用流式下载追踪进度
                const contentLength = response.headers.get('Content-Length');
                const total = contentLength ? parseInt(contentLength, 10) : 0;
                let loaded = 0;
                
                const reader = response.body.getReader();
                const chunks = [];
                
                while (true) {
                    const { done, value } = await reader.read();
                    
                    if (done) break;
                    
                    chunks.push(value);
                    loaded += value.length;
                    
                    // 更新进度
                    const progressText = document.getElementById(`progress-text-${index}`);
                    const progressFill = document.getElementById(`progress-fill-${index}`);
                    
                    if (progressText && progressFill) {
                        if (total > 0) {
                            const percent = Math.round((loaded / total) * 100);
                            progressText.textContent = `下载中: ${percent}% (${(loaded / 1024 / 1024).toFixed(2)}MB / ${(total / 1024 / 1024).toFixed(2)}MB)`;
                            progressFill.style.width = `${percent}%`;
                        } else {
                            progressText.textContent = `下载中: ${(loaded / 1024 / 1024).toFixed(2)}MB`;
                        }
                    }
                }
                
                // 组合所有数据块
                const blob = new Blob(chunks);
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                
                // 从Content-Disposition header获取文件名
                const contentDisposition = response.headers.get('Content-Disposition');
                let filename = `${title}.mp3`;
                
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
                window.URL.revokeObjectURL(url);
                
                // 显示完成状态（使用之前已声明的变量）
                const progressText = document.getElementById(`progress-text-${index}`);
                const progressFill = document.getElementById(`progress-fill-${index}`);
                
                if (progressText && progressFill) {
                    progressText.textContent = '下载完成！';
                    progressFill.style.width = '100%';
                }
                
                if (statusHint) {
                    statusHint.innerHTML = '✅ 全部完成！';
                }
                
                buttons[index].textContent = '下载完成';
                setTimeout(() => {
                    if (progressContainer && progressContainer.parentNode) {
                        progressContainer.remove();
                    }
                    if (statusHint && statusHint.parentNode) {
                        statusHint.remove();
                    }
                    buttons[index].textContent = originalText;
                    buttons[index].disabled = false;
                }, 2000);
            } else {
                const data = await response.json();
                alert('下载失败: ' + (data.error || '未知错误'));
                
                // 清理状态提示（使用之前已声明的statusHint变量）
                if (statusHint && statusHint.parentNode) {
                    statusHint.remove();
                }
                
                buttons[index].textContent = originalText;
                buttons[index].disabled = false;
            }
        }
    } catch (error) {
        alert('下载失败: ' + error.message);
        const buttons = document.querySelectorAll('.episode-item button.download-btn');
        if (buttons[index]) {
            const originalText = buttons[index].getAttribute('data-original-text') || '下载';
            buttons[index].textContent = originalText;
            buttons[index].disabled = false;
            
            // 清理状态提示（在catch块中需要重新获取，因为statusHint可能不在作用域内）
            const errorStatusHint = document.getElementById(`status-hint-${index}`);
            if (errorStatusHint && errorStatusHint.parentNode) {
                errorStatusHint.remove();
            }
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
let selectedDownloads = new Set(); // 存储选中的文件ID
let currentDownloadUser = ''; // 当前筛选的用户

async function loadDownloads(username = '') {
    try {
        currentDownloadUser = username;
        const url = username ? apiUrl(`/api/downloads?username=${encodeURIComponent(username)}`) : apiUrl('/api/downloads');
        const response = await fetch(url);
        const data = await response.json();
        
        if (response.ok) {
            const listDiv = document.getElementById('downloads-list');
            
            // 构建用户过滤器和批量操作工具栏
            const toolbar = `
                <div class="downloads-toolbar">
                    <div class="filter-group">
                        <label for="user-filter">用户筛选：</label>
                        <select id="user-filter" onchange="filterByUser(this.value)">
                            <option value="">全部用户</option>
                            ${data.users.map(user => 
                                `<option value="${user}" ${user === username ? 'selected' : ''}>${user}</option>`
                            ).join('')}
                        </select>
                        <span style="margin-left: 15px; color: #666;">共 ${data.downloads.length} 个文件</span>
                        <button onclick="selectAll()" class="select-all-btn">全选</button>
                    </div>
                    <div class="batch-actions" style="display: none;">
                        <span id="selected-count">已选择 0 项</span>
                        <button onclick="batchDownload()" class="batch-btn download-btn">批量下载</button>
                        <button onclick="batchConvert()" class="batch-btn monitor-btn">转MP3下载</button>
                        <button onclick="batchDelete()" class="batch-btn delete-btn">批量删除</button>
                        <button onclick="clearSelection()" class="batch-btn">取消选择</button>
                    </div>
                </div>
            `;
            
            if (data.downloads.length === 0) {
                listDiv.innerHTML = toolbar + '<p style="margin-top: 20px;">暂无下载文件</p>';
            } else {
                const downloadsList = data.downloads.map((download, index) => {
                    const size = (download.size / 1024 / 1024).toFixed(2);
                    const episodeInfo = download.episode_info || {};
                    const fileExt = download.filename.split('.').pop().toLowerCase();
                    const isM4A = fileExt === 'm4a';
                    const username = download.username || 'unknown';
                    const isChecked = selectedDownloads.has(download.file_id);
                    
                    // 构建详情内容（包括描述和封面）
                    const hasDetails = (episodeInfo.description && episodeInfo.description.trim()) || episodeInfo.cover;
                    let detailsContent = '';
                    
                    if (hasDetails) {
                        if (episodeInfo.cover) {
                            detailsContent += `<img src="${episodeInfo.cover}" alt="封面" class="episode-detail-cover" onerror="this.style.display='none'">`;
                        }
                        if (episodeInfo.description) {
                            detailsContent += `<p class="episode-description">${episodeInfo.description}</p>`;
                        }
                    }
                    
                    return `
                        <div class="download-item ${isChecked ? 'selected' : ''}" data-file-id="${download.file_id}">
                            <div class="download-item-checkbox">
                                <input type="checkbox" id="check-${download.file_id}" 
                                       ${isChecked ? 'checked' : ''}
                                       onchange="toggleDownloadSelection('${download.file_id}')"
                                       onclick="event.stopPropagation()">
                            </div>
                            <div class="download-item-info">
                                <h5>
                                    ${episodeInfo.title || download.filename}
                                    <span class="user-badge">${username}</span>
                                </h5>
                                ${episodeInfo.podcast_title ? `<p class="podcast-channel">频道: ${episodeInfo.podcast_title}</p>` : ''}
                                <p class="file-meta">
                                    大小: ${size} MB | 格式: ${fileExt.toUpperCase()} | 下载时间: ${new Date(download.downloaded_at).toLocaleString('zh-CN')}
                                </p>
                                ${hasDetails ? `
                                    <div class="details-container">
                                        <button class="expand-btn" id="expand-btn-${download.file_id}" onclick="toggleDescription('${download.file_id}', event)">
                                            展开详情 ▼
                                        </button>
                                        <div class="details-content" id="details-${download.file_id}" style="display: none;">
                                            ${detailsContent}
                                        </div>
                                    </div>
                                ` : ''}
                            </div>
                            <div class="download-item-actions">
                                <a href="${apiUrl('/downloads/' + download.file_id)}" download class="download-btn">下载</a>
                                ${isM4A ? `<button onclick="convertToMp3('${download.file_id}')" class="monitor-btn">转MP3</button>` : ''}
                                <button onclick="deleteDownload('${download.file_id}')" class="delete-btn">删除</button>
                            </div>
                        </div>
                    `;
                }).join('');
                
                listDiv.innerHTML = toolbar + downloadsList;
                
                // 更新批量操作工具栏显示
                updateBatchToolbar();
            }
        }
    } catch (error) {
        console.error('加载下载列表失败:', error);
    }
}

// 切换描述展开/收起
function toggleDescription(fileId, event) {
    event.stopPropagation();
    const details = document.getElementById(`details-${fileId}`);
    const btn = document.getElementById(`expand-btn-${fileId}`);
    
    if (!details || !btn) return;
    
    if (details.style.display === 'none') {
        details.style.display = 'block';
        btn.textContent = '收起详情 ▲';
        btn.classList.add('expanded');
    } else {
        details.style.display = 'none';
        btn.textContent = '展开详情 ▼';
        btn.classList.remove('expanded');
    }
}

// 按用户过滤
function filterByUser(username) {
    loadDownloads(username);
}

// 切换下载项选择状态
function toggleDownloadSelection(fileId) {
    const checkbox = document.getElementById(`check-${fileId}`);
    const downloadItem = document.querySelector(`[data-file-id="${fileId}"]`);
    
    if (checkbox.checked) {
        selectedDownloads.add(fileId);
        downloadItem.classList.add('selected');
    } else {
        selectedDownloads.delete(fileId);
        downloadItem.classList.remove('selected');
    }
    
    updateBatchToolbar();
}

// 更新批量操作工具栏
function updateBatchToolbar() {
    const batchActions = document.querySelector('.batch-actions');
    const selectedCount = document.getElementById('selected-count');
    
    if (batchActions && selectedCount) {
        if (selectedDownloads.size > 0) {
            batchActions.style.display = 'flex';
            selectedCount.textContent = `已选择 ${selectedDownloads.size} 项`;
        } else {
            batchActions.style.display = 'none';
        }
    }
}

// 全选
function selectAll() {
    const checkboxes = document.querySelectorAll('.download-item-checkbox input[type="checkbox"]');
    checkboxes.forEach(cb => {
        cb.checked = true;
        const fileId = cb.id.replace('check-', '');
        selectedDownloads.add(fileId);
        const downloadItem = document.querySelector(`[data-file-id="${fileId}"]`);
        if (downloadItem) {
            downloadItem.classList.add('selected');
        }
    });
    updateBatchToolbar();
}

// 清除选择
function clearSelection() {
    selectedDownloads.clear();
    document.querySelectorAll('.download-item-checkbox input[type="checkbox"]').forEach(cb => {
        cb.checked = false;
    });
    document.querySelectorAll('.download-item').forEach(item => {
        item.classList.remove('selected');
    });
    updateBatchToolbar();
}

// 批量下载
async function batchDownload() {
    if (selectedDownloads.size === 0) {
        alert('请先选择要下载的文件');
        return;
    }
    
    // 依次触发下载
    for (const fileId of selectedDownloads) {
        const link = document.createElement('a');
        link.href = apiUrl(`/downloads/${fileId}`);
        link.download = '';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        // 延迟一下，避免浏览器阻止多个下载
        await new Promise(resolve => setTimeout(resolve, 500));
    }
    
    alert(`已触发${selectedDownloads.size}个文件的下载`);
}

// 批量转换为MP3并下载
async function batchConvert() {
    if (selectedDownloads.size === 0) {
        alert('请先选择要处理的文件');
        return;
    }
    
    if (!confirm(`确定要处理选中的${selectedDownloads.size}个文件吗？\n\nMP3文件将直接下载，M4A文件将转换为MP3后自动下载。\n注意：转换可能需要一些时间，请耐心等待。`)) {
        return;
    }
    
    try {
        const response = await fetch(apiUrl('/api/audio/batch/convert'), {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                file_ids: Array.from(selectedDownloads)
            })
        });
        
        // 检查响应的Content-Type
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            const text = await response.text();
            console.error('服务器返回非JSON响应:', text.substring(0, 200));
            alert('服务器错误：返回了非JSON响应。请查看浏览器控制台获取详细信息。');
            return;
        }
        
        const data = await response.json();
        
        if (response.ok) {
            // 显示详细结果
            let message = data.message + `\n\n总计: ${data.total_count} 个文件\n成功: ${data.success_count} 个\n失败: ${data.total_count - data.success_count} 个`;
            
            // 如果有失败的，显示失败原因
            if (data.results) {
                const failedResults = data.results.filter(r => !r.success);
                if (failedResults.length > 0) {
                    message += '\n\n失败详情：';
                    failedResults.forEach((r, idx) => {
                        if (idx < 5) { // 只显示前5个失败项
                            message += `\n- ${r.error}`;
                        }
                    });
                    if (failedResults.length > 5) {
                        message += `\n... 还有${failedResults.length - 5}个失败项`;
                    }
                }
            }
            
            // 自动触发下载成功的文件
            if (data.results) {
                const successResults = data.results.filter(r => r.success);
                if (successResults.length > 0) {
                    message += `\n\n正在自动下载${successResults.length}个MP3文件...`;
                    alert(message);
                    
                    // 直接自动下载，不再询问
                    for (const result of successResults) {
                        const fileId = result.new_file_id || result.file_id;
                        const link = document.createElement('a');
                        link.href = apiUrl(`/downloads/${fileId}`);
                        link.download = '';
                        document.body.appendChild(link);
                        link.click();
                        document.body.removeChild(link);
                        
                        // 延迟避免浏览器阻止
                        await new Promise(resolve => setTimeout(resolve, 500));
                    }
                } else {
                    // 全部失败才显示alert
                    alert(message);
                }
            } else {
                alert(message);
            }
            
            // 刷新列表并清除选择
            await loadDownloads(currentDownloadUser);
            clearSelection();
        } else {
            alert('批量处理失败: ' + (data.error || '未知错误'));
        }
    } catch (error) {
        console.error('批量处理异常:', error);
        alert('请求失败: ' + error.message + '\n\n请查看浏览器控制台获取详细错误信息。');
    }
}

// 批量删除
async function batchDelete() {
    if (selectedDownloads.size === 0) {
        alert('请先选择要删除的文件');
        return;
    }
    
    if (!confirm(`确定要删除选中的${selectedDownloads.size}个文件吗？此操作不可恢复！`)) {
        return;
    }
    
    try {
        const response = await fetch(apiUrl('/api/downloads/batch/delete'), {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                file_ids: Array.from(selectedDownloads)
            })
        });
        
        // 检查响应的Content-Type
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            const text = await response.text();
            console.error('服务器返回非JSON响应:', text.substring(0, 200));
            alert('服务器错误：返回了非JSON响应。请查看浏览器控制台获取详细信息。');
            return;
        }
        
        const data = await response.json();
        
        if (response.ok) {
            let message = data.message;
            if (data.failed_count > 0) {
                message += `\n\n失败: ${data.failed_count} 个文件`;
            }
            alert(message);
            clearSelection();
            loadDownloads(currentDownloadUser);
        } else {
            alert('批量删除失败: ' + (data.error || '未知错误'));
        }
    } catch (error) {
        console.error('批量删除异常:', error);
        alert('请求失败: ' + error.message + '\n\n请查看浏览器控制台获取详细错误信息。');
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


