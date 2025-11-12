from flask import Flask, render_template, request, jsonify, send_file
import os
import json
import threading
import time
import requests
import logging
from datetime import datetime
from werkzeug.middleware.proxy_fix import ProxyFix
from utils.xiaoyuzhou import get_episode_info, get_download_url
from utils.opml_parser import parse_opml
from utils.rss_parser import parse_rss_feed, get_episodes_from_rss
from utils.download_manager import DownloadManager
from utils.task_manager import TaskManager
from utils.audio_converter import convert_m4a_to_mp3, get_audio_format, check_ffmpeg

# 配置日志
log_dir = os.getenv('LOG_DIR', '.')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, 'app.log')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# 支持反向代理路径前缀
# 通过环境变量 APPLICATION_ROOT 或 SCRIPT_NAME 设置，例如: /podcast
application_root = os.getenv('APPLICATION_ROOT', os.getenv('SCRIPT_NAME', ''))
if application_root:
    # 确保以 / 开头，不以 / 结尾
    application_root = '/' + application_root.strip('/')
    app.config['APPLICATION_ROOT'] = application_root
    logger.info(f"设置应用根路径: {application_root}")
else:
    application_root = ''

# 配置ProxyFix以正确处理反向代理
# 如果使用反向代理，设置环境变量 PROXY_FIX=1
if os.getenv('PROXY_FIX', '').lower() in ('1', 'true', 'yes'):
    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=1,
        x_proto=1,
        x_host=1,
        x_port=1,
        x_prefix=1
    )
    logger.info("已启用ProxyFix中间件")

# 添加模板上下文处理器，确保url_for正确处理路径前缀
@app.context_processor
def inject_application_root():
    """注入应用根路径到所有模板"""
    return {
        'application_root': application_root,
        'url_prefix': application_root  # 提供url_prefix别名
    }

# 修改url_for使其支持路径前缀
from flask import url_for as flask_url_for
@app.template_global()
def url_for(endpoint, **values):
    """重写url_for以支持路径前缀"""
    if endpoint == 'static':
        # 静态文件直接拼接路径
        filename = values.get('filename', '')
        return f"{application_root}/static/{filename}"
    # 其他路由使用Flask原生url_for
    url = flask_url_for(endpoint, **values)
    # 如果URL不是以application_root开头，添加前缀
    if application_root and not url.startswith(application_root):
        url = application_root + url
    return url

app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['DOWNLOAD_FOLDER'] = 'downloads'
app.config['USERS_FOLDER'] = 'users'

# 确保必要的文件夹存在
for folder in [app.config['UPLOAD_FOLDER'], app.config['DOWNLOAD_FOLDER'], app.config['USERS_FOLDER']]:
    os.makedirs(folder, exist_ok=True)

# 初始化管理器
download_manager = DownloadManager(app.config['DOWNLOAD_FOLDER'])
task_manager = TaskManager(download_manager)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/episode/info', methods=['POST'])
def get_episode_info_api():
    """获取单集节目信息"""
    data = request.json
    episode_url = data.get('url', '').strip()
    
    if not episode_url:
        return jsonify({'error': '请提供节目链接'}), 400
    
    try:
        info = get_episode_info(episode_url)
        if info:
            return jsonify(info)
        else:
            return jsonify({'error': '无法获取节目信息'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/episode/download-url', methods=['POST'])
def get_download_url_api():
    """获取单集节目下载链接"""
    data = request.json
    episode_url = data.get('url', '').strip()
    
    if not episode_url:
        return jsonify({'error': '请提供节目链接'}), 400
    
    try:
        download_url = get_download_url(episode_url)
        if download_url:
            return jsonify({'download_url': download_url})
        else:
            return jsonify({'error': '无法获取下载链接'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/episode/download', methods=['POST'])
def download_episode_file():
    """
    下载音频文件并设置正确的文件名
    注意：此接口使用流式传输，不会创建临时文件，数据直接从源服务器流式传输到客户端
    """
    from flask import Response
    import re
    from urllib.parse import quote
    import tempfile
    
    data = request.json
    audio_url = data.get('url', '').strip()
    filename = data.get('filename', 'episode').strip()
    convert_to_mp3 = data.get('convert_to_mp3', False)  # 是否转换为mp3
    
    if not audio_url:
        return jsonify({'error': '请提供音频链接'}), 400
    
    try:
        # 清理文件名，移除非法字符
        safe_filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        safe_filename = safe_filename.strip()[:100]  # 限制长度
        
        # 下载文件
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(audio_url, headers=headers, stream=True, timeout=30)
        response.raise_for_status()
        
        # 获取文件大小
        content_length = response.headers.get('Content-Length')
        
        # 确定文件扩展名
        content_type = response.headers.get('Content-Type', '')
        if 'mp3' in content_type or audio_url.endswith('.mp3'):
            ext = 'mp3'
        elif 'm4a' in content_type or audio_url.endswith('.m4a'):
            ext = 'm4a'
        elif 'aac' in content_type or audio_url.endswith('.aac'):
            ext = 'aac'
        else:
            ext = 'mp3'  # 默认
        
        # 如果需要转换且文件是m4a格式
        if convert_to_mp3 and ext == 'm4a':
            if not check_ffmpeg():
                return jsonify({'error': 'ffmpeg未安装，无法转换格式。请安装ffmpeg或取消转换选项。'}), 400
            
            # 创建临时文件保存m4a
            with tempfile.NamedTemporaryFile(delete=False, suffix='.m4a') as temp_m4a:
                temp_m4a_path = temp_m4a.name
                # 下载到临时文件
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        temp_m4a.write(chunk)
                temp_m4a.close()
            
            try:
                # 转换为mp3
                temp_mp3_path = temp_m4a_path.replace('.m4a', '.mp3')
                logger.info(f"开始转换音频文件: {temp_m4a_path} -> {temp_mp3_path}")
                success, output_path, error = convert_m4a_to_mp3(temp_m4a_path, temp_mp3_path)
                
                if not success:
                    logger.error(f"音频转换失败 - 输入文件: {temp_m4a_path}, 错误信息: {error}")
                    os.unlink(temp_m4a_path)  # 清理临时文件
                    return jsonify({'error': f'转换失败: {error}'}), 500
                
                logger.info(f"音频转换成功: {output_path}")
                
                # 读取转换后的mp3文件并流式传输
                def generate():
                    try:
                        with open(temp_mp3_path, 'rb') as f:
                            while True:
                                chunk = f.read(8192)
                                if not chunk:
                                    break
                                yield chunk
                    finally:
                        # 清理临时文件
                        if os.path.exists(temp_m4a_path):
                            os.unlink(temp_m4a_path)
                        if os.path.exists(temp_mp3_path):
                            os.unlink(temp_mp3_path)
                
                ext = 'mp3'
                content_type = 'audio/mpeg'
                # 对于转换后的文件，获取文件大小
                content_length = str(os.path.getsize(temp_mp3_path)) if os.path.exists(temp_mp3_path) else None
            except Exception as e:
                # 记录详细错误信息
                logger.exception(f"音频转换过程发生异常 - 输入文件: {temp_m4a_path}, 异常信息: {str(e)}")
                # 确保清理临时文件
                if os.path.exists(temp_m4a_path):
                    os.unlink(temp_m4a_path)
                if 'temp_mp3_path' in locals() and os.path.exists(temp_mp3_path):
                    os.unlink(temp_mp3_path)
                return jsonify({'error': f'转换过程出错: {str(e)}'}), 500
        else:
            # 直接流式传输，不创建临时文件
            def generate():
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        yield chunk
        
        # 使用RFC 5987格式支持中文文件名
        # HTTP头必须使用latin-1编码，所以filename部分只使用ASCII字符
        # 中文文件名使用filename*=UTF-8''格式
        full_filename = f'{safe_filename}.{ext}'
        encoded_full_filename = quote(full_filename.encode('utf-8'))
        
        # 创建一个ASCII安全的文件名（用于兼容性）
        ascii_filename = safe_filename.encode('ascii', 'ignore').decode('ascii') or 'episode'
        if not ascii_filename:
            ascii_filename = 'episode'
        ascii_full_filename = f'{ascii_filename}.{ext}'
        
        # 构建响应头
        response_headers = {
            'Content-Disposition': f'attachment; filename="{ascii_full_filename}"; filename*=UTF-8\'\'{encoded_full_filename}'
        }
        
        # 如果有文件大小信息，添加到响应头
        if content_length:
            response_headers['Content-Length'] = content_length
        
        return Response(
            generate(),
            mimetype=content_type or 'audio/mpeg',
            headers=response_headers
        )
    except Exception as e:
        return jsonify({'error': f'下载失败: {str(e)}'}), 500

@app.route('/api/user/create', methods=['POST'])
def create_user():
    """创建用户"""
    data = request.json
    username = data.get('username', '').strip()
    
    if not username:
        return jsonify({'error': '请提供用户名'}), 400
    
    user_file = os.path.join(app.config['USERS_FOLDER'], f'{username}.json')
    if os.path.exists(user_file):
        # 如果用户已存在，返回用户信息
        with open(user_file, 'r', encoding='utf-8') as f:
            user_data = json.load(f)
        return jsonify({
            'message': '用户已存在，已加载',
            'username': username,
            'subscriptions': user_data.get('subscriptions', [])
        })
    
    user_data = {
        'username': username,
        'created_at': datetime.now().isoformat(),
        'subscriptions': [],
        'tasks': []
    }
    
    with open(user_file, 'w', encoding='utf-8') as f:
        json.dump(user_data, f, ensure_ascii=False, indent=2)
    
    return jsonify({'message': '用户创建成功', 'username': username})

@app.route('/api/users', methods=['GET'])
def list_users():
    """列出所有用户"""
    users = []
    if os.path.exists(app.config['USERS_FOLDER']):
        for filename in os.listdir(app.config['USERS_FOLDER']):
            if filename.endswith('.json'):
                username = filename[:-5]  # 移除.json后缀
                user_file = os.path.join(app.config['USERS_FOLDER'], filename)
                try:
                    with open(user_file, 'r', encoding='utf-8') as f:
                        user_data = json.load(f)
                    users.append({
                        'username': username,
                        'created_at': user_data.get('created_at', ''),
                        'subscriptions_count': len(user_data.get('subscriptions', []))
                    })
                except:
                    pass
    return jsonify({'users': users})

@app.route('/api/user/<username>/opml', methods=['POST'])
def upload_opml(username):
    """上传OPML文件"""
    if 'file' not in request.files:
        return jsonify({'error': '请上传OPML文件'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '文件名为空'}), 400
    
    try:
        opml_content = file.read().decode('utf-8')
        subscriptions = parse_opml(opml_content)
        
        # 保存订阅信息到用户文件
        user_file = os.path.join(app.config['USERS_FOLDER'], f'{username}.json')
        if not os.path.exists(user_file):
            return jsonify({'error': '用户不存在'}), 404
        
        with open(user_file, 'r', encoding='utf-8') as f:
            user_data = json.load(f)
        
        user_data['subscriptions'] = subscriptions
        user_data['updated_at'] = datetime.now().isoformat()
        
        with open(user_file, 'w', encoding='utf-8') as f:
            json.dump(user_data, f, ensure_ascii=False, indent=2)
        
        return jsonify({
            'message': 'OPML文件解析成功',
            'subscriptions': subscriptions
        })
    except Exception as e:
        return jsonify({'error': f'解析OPML文件失败: {str(e)}'}), 500

@app.route('/api/user/<username>/subscriptions', methods=['GET'])
def get_subscriptions(username):
    """获取用户的订阅列表"""
    user_file = os.path.join(app.config['USERS_FOLDER'], f'{username}.json')
    if not os.path.exists(user_file):
        return jsonify({'error': '用户不存在'}), 404
    
    with open(user_file, 'r', encoding='utf-8') as f:
        user_data = json.load(f)
    
    return jsonify({
        'subscriptions': user_data.get('subscriptions', [])
    })

@app.route('/api/user/<username>/subscriptions/<int:sub_id>/episodes', methods=['GET'])
def get_subscription_episodes(username, sub_id):
    """获取订阅的节目列表"""
    user_file = os.path.join(app.config['USERS_FOLDER'], f'{username}.json')
    if not os.path.exists(user_file):
        return jsonify({'error': '用户不存在'}), 404
    
    with open(user_file, 'r', encoding='utf-8') as f:
        user_data = json.load(f)
    
    subscriptions = user_data.get('subscriptions', [])
    if sub_id >= len(subscriptions):
        return jsonify({'error': '订阅不存在'}), 404
    
    subscription = subscriptions[sub_id]
    rss_url = subscription.get('xmlUrl', '')
    
    try:
        episodes = get_episodes_from_rss(rss_url)
        return jsonify({
            'subscription': subscription,
            'episodes': episodes
        })
    except Exception as e:
        return jsonify({'error': f'获取节目列表失败: {str(e)}'}), 500

@app.route('/api/user/<username>/download/latest', methods=['POST'])
def download_latest(username):
    """下载最新N集节目"""
    data = request.json or {}
    count = int(data.get('count', 5))
    convert_to_mp3 = data.get('convert_to_mp3', False)
    
    user_file = os.path.join(app.config['USERS_FOLDER'], f'{username}.json')
    if not os.path.exists(user_file):
        return jsonify({'error': '用户不存在'}), 404
    
    with open(user_file, 'r', encoding='utf-8') as f:
        user_data = json.load(f)
    
    subscriptions = user_data.get('subscriptions', [])
    
    task_id = task_manager.create_download_latest_task(username, subscriptions, count, convert_to_mp3)
    
    return jsonify({
        'message': '下载任务已创建',
        'task_id': task_id
    })

@app.route('/api/user/<username>/monitor/start', methods=['POST'])
def start_monitor(username):
    """启动监听任务"""
    data = request.json or {}
    convert_to_mp3 = data.get('convert_to_mp3', False)
    
    user_file = os.path.join(app.config['USERS_FOLDER'], f'{username}.json')
    if not os.path.exists(user_file):
        return jsonify({'error': '用户不存在'}), 404
    
    with open(user_file, 'r', encoding='utf-8') as f:
        user_data = json.load(f)
    
    subscriptions = user_data.get('subscriptions', [])
    
    task_id = task_manager.create_monitor_task(username, subscriptions, convert_to_mp3)
    
    return jsonify({
        'message': '监听任务已启动',
        'task_id': task_id
    })

@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    """获取所有任务"""
    tasks = task_manager.get_all_tasks()
    return jsonify({'tasks': tasks})

@app.route('/api/tasks/<task_id>', methods=['GET'])
def get_task(task_id):
    """获取任务详情"""
    task = task_manager.get_task(task_id)
    if task:
        return jsonify(task)
    else:
        return jsonify({'error': '任务不存在'}), 404

@app.route('/api/tasks/<task_id>/cancel', methods=['POST'])
def cancel_task(task_id):
    """取消任务"""
    success = task_manager.cancel_task(task_id)
    if success:
        return jsonify({'message': '任务已取消'})
    else:
        return jsonify({'error': '任务不存在或无法取消'}), 404

@app.route('/api/downloads', methods=['GET'])
def get_downloads():
    """获取已下载的文件，支持按用户过滤"""
    username = request.args.get('username')  # 可选的用户名过滤参数
    downloads = download_manager.list_downloads(username=username)
    users = download_manager.get_users()  # 获取所有用户列表
    return jsonify({
        'downloads': downloads,
        'users': users
    })

@app.route('/api/downloads/<file_id>', methods=['DELETE'])
def delete_download(file_id):
    """删除已下载的文件"""
    success = download_manager.delete_file(file_id)
    if success:
        return jsonify({'message': '文件已删除'})
    else:
        return jsonify({'error': '文件不存在'}), 404

@app.route('/downloads/<file_id>', methods=['GET'])
def download_file(file_id):
    """下载文件"""
    from flask import Response
    from urllib.parse import quote
    
    file_info = download_manager.metadata.get(file_id)
    if file_info and os.path.exists(file_info['file_path']):
        # 优先使用节目标题作为文件名
        episode_info = file_info.get('episode_info', {})
        if episode_info and episode_info.get('title'):
            # 从标题生成安全的文件名
            import re
            safe_title = re.sub(r'[<>:"/\\|?*]', '_', episode_info['title'])
            safe_title = safe_title.strip()[:100]  # 限制长度
            # 保持原文件扩展名
            ext = os.path.splitext(file_info['filename'])[1]
            filename = f"{safe_title}{ext}"
        else:
            filename = file_info['filename']
        
        # 使用RFC 5987格式支持中文文件名
        encoded_filename = quote(filename.encode('utf-8'))
        ascii_filename = filename.encode('ascii', 'ignore').decode('ascii') or 'download'
        
        response = send_file(
            file_info['file_path'],
            as_attachment=True,
            download_name=filename
        )
        
        # 添加正确的Content-Disposition头支持中文
        response.headers['Content-Disposition'] = f'attachment; filename="{ascii_filename}"; filename*=UTF-8\'\'{encoded_filename}'
        
        return response
    else:
        return jsonify({'error': '文件不存在'}), 404

@app.route('/api/audio/convert', methods=['POST'])
def convert_audio():
    """转换音频格式（m4a转mp3）"""
    data = request.json
    file_id = data.get('file_id')
    
    if not file_id:
        return jsonify({'error': '请提供文件ID'}), 400
    
    file_info = download_manager.metadata.get(file_id)
    if not file_info or not os.path.exists(file_info['file_path']):
        return jsonify({'error': '文件不存在'}), 404
    
    file_path = file_info['file_path']
    audio_format = get_audio_format(file_path)
    
    if audio_format != 'm4a':
        return jsonify({'error': f'当前文件格式为{audio_format}，只能转换m4a格式'}), 400
    
    if not check_ffmpeg():
        return jsonify({'error': 'ffmpeg未安装，无法转换格式'}), 400
    
    # 生成输出路径
    base_name = os.path.splitext(file_path)[0]
    output_path = f"{base_name}.mp3"
    
    # 执行转换
    logger.info(f"开始转换音频文件 - 文件ID: {file_id}, 输入文件: {file_path}, 输出文件: {output_path}")
    success, converted_path, error = convert_m4a_to_mp3(file_path, output_path)
    
    if success:
        # 删除原始文件
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"已删除原始文件: {file_path}")
        except Exception as e:
            logger.warning(f"删除原始文件失败: {file_path}, 错误: {str(e)}")
        
        # 更新元数据（保持原file_id，替换文件信息）
        new_filename = os.path.basename(converted_path)
        download_manager.metadata[file_id]['filename'] = new_filename
        download_manager.metadata[file_id]['file_path'] = converted_path
        download_manager.metadata[file_id]['size'] = os.path.getsize(converted_path)
        download_manager.metadata[file_id]['downloaded_at'] = datetime.now().isoformat()
        download_manager._save_metadata()
        
        logger.info(f"音频转换成功并替换原文件 - 文件ID: {file_id}, 输出文件: {converted_path}")
        return jsonify({
            'message': '转换成功',
            'file_id': file_id,
            'file_path': converted_path,
            'filename': new_filename
        })
    else:
        logger.error(f"音频转换失败 - 文件ID: {file_id}, 输入文件: {file_path}, 错误信息: {error}")
        return jsonify({'error': f'转换失败: {error}'}), 500

@app.route('/api/downloads/batch/delete', methods=['POST'])
def batch_delete_downloads():
    """批量删除下载文件"""
    try:
        data = request.json
        if not data:
            return jsonify({'error': '请求数据为空'}), 400
            
        file_ids = data.get('file_ids', [])
        
        if not file_ids:
            return jsonify({'error': '请提供要删除的文件ID列表'}), 400
        
        success_count, failed_ids = download_manager.delete_files_batch(file_ids)
        
        return jsonify({
            'message': f'成功删除{success_count}个文件',
            'success_count': success_count,
            'failed_count': len(failed_ids),
            'failed_ids': failed_ids
        })
    except Exception as e:
        logger.error(f"批量删除文件失败: {str(e)}")
        return jsonify({'error': f'批量删除失败: {str(e)}'}), 500

@app.route('/api/audio/batch/convert', methods=['POST'])
def batch_convert_audio():
    """批量转换音频格式（m4a转mp3）"""
    try:
        data = request.json
        if not data:
            return jsonify({'error': '请求数据为空'}), 400
            
        file_ids = data.get('file_ids', [])
        
        if not file_ids:
            return jsonify({'error': '请提供要转换的文件ID列表'}), 400
        
        if not check_ffmpeg():
            return jsonify({'error': 'ffmpeg未安装，无法转换格式'}), 400
        
        results = []
        success_count = 0
        
        for file_id in file_ids:
            try:
                file_info = download_manager.metadata.get(file_id)
                if not file_info or not os.path.exists(file_info['file_path']):
                    results.append({
                        'file_id': file_id,
                        'success': False,
                        'error': '文件不存在'
                    })
                    continue
                
                file_path = file_info['file_path']
                audio_format = get_audio_format(file_path)
                
                # 如果已经是MP3，直接标记为成功，不需要转换
                if audio_format == 'mp3':
                    results.append({
                        'file_id': file_id,
                        'new_file_id': file_id,
                        'success': True,
                        'filename': file_info['filename'],
                        'already_mp3': True
                    })
                    success_count += 1
                    continue
                
                # 如果不是m4a也不是mp3，报错
                if audio_format != 'm4a':
                    results.append({
                        'file_id': file_id,
                        'success': False,
                        'error': f'文件格式为{audio_format}，只能处理mp3和m4a格式'
                    })
                    continue
                
                # 生成输出路径
                base_name = os.path.splitext(file_path)[0]
                output_path = f"{base_name}.mp3"
                
                # 执行转换
                logger.info(f"批量转换 - 文件ID: {file_id}, 输入: {file_path}, 输出: {output_path}")
                success, converted_path, error = convert_m4a_to_mp3(file_path, output_path)
                
                if success:
                    # 删除原始文件
                    try:
                        if os.path.exists(file_path):
                            os.remove(file_path)
                            logger.info(f"批量转换 - 已删除原始文件: {file_path}")
                    except Exception as e:
                        logger.warning(f"批量转换 - 删除原始文件失败: {file_path}, 错误: {str(e)}")
                    
                    # 更新元数据（保持原file_id，替换文件信息）
                    new_filename = os.path.basename(converted_path)
                    download_manager.metadata[file_id]['filename'] = new_filename
                    download_manager.metadata[file_id]['file_path'] = converted_path
                    download_manager.metadata[file_id]['size'] = os.path.getsize(converted_path)
                    download_manager.metadata[file_id]['downloaded_at'] = datetime.now().isoformat()
                    download_manager._save_metadata()
                    success_count += 1
                    results.append({
                        'file_id': file_id,
                        'success': True,
                        'filename': new_filename
                    })
                else:
                    results.append({
                        'file_id': file_id,
                        'success': False,
                        'error': error
                    })
            except Exception as e:
                logger.error(f"批量转换单个文件时出错 - 文件ID: {file_id}, 错误: {str(e)}")
                results.append({
                    'file_id': file_id,
                    'success': False,
                    'error': str(e)
                })
        
        return jsonify({
            'message': f'成功转换{success_count}个文件',
            'success_count': success_count,
            'total_count': len(file_ids),
            'results': results
        })
    except Exception as e:
        logger.error(f"批量转换音频失败: {str(e)}")
        return jsonify({'error': f'批量转换失败: {str(e)}'}), 500

@app.route('/api/ffmpeg/check', methods=['GET'])
def check_ffmpeg_api():
    """检查ffmpeg是否可用"""
    available = check_ffmpeg()
    return jsonify({
        'available': available,
        'message': 'ffmpeg可用' if available else 'ffmpeg未安装或不在PATH中'
    })

if __name__ == '__main__':
    # 启动后台任务处理线程
    task_manager.start_background_thread()
    app.run(debug=True, host='0.0.0.0', port=5000)

