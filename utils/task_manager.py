"""
任务管理器
"""
import threading
import time
import uuid
import os
import logging
from datetime import datetime
from utils.rss_parser import get_episodes_from_rss, check_rss_update
from utils.download_manager import DownloadManager
from utils.audio_converter import convert_m4a_to_mp3, get_audio_format, check_ffmpeg

logger = logging.getLogger(__name__)

class TaskManager:
    def __init__(self, download_manager):
        self.download_manager = download_manager
        self.tasks = {}
        self.running = False
        self.thread = None
        self.lock = threading.Lock()
    
    def create_download_latest_task(self, username, subscriptions, count, convert_to_mp3=False):
        """创建下载最新N集任务"""
        task_id = str(uuid.uuid4())
        
        task = {
            'task_id': task_id,
            'username': username,
            'type': 'download_latest',
            'status': 'pending',
            'created_at': datetime.now().isoformat(),
            'subscriptions': subscriptions,
            'count': count,
            'convert_to_mp3': convert_to_mp3,
            'progress': {
                'total': len(subscriptions) * count,  # 修复：总数应该是订阅数 * 每个订阅的集数
                'completed': 0,
                'failed': 0
            },
            'results': []
        }
        
        with self.lock:
            self.tasks[task_id] = task
        
        # 立即开始执行任务
        self._execute_download_latest_task(task_id)
        
        return task_id
    
    def create_monitor_task(self, username, subscriptions, convert_to_mp3=False):
        """创建监听任务"""
        task_id = str(uuid.uuid4())
        
        task = {
            'task_id': task_id,
            'username': username,
            'type': 'monitor',
            'status': 'running',
            'created_at': datetime.now().isoformat(),
            'last_check': datetime.now().isoformat(),
            'subscriptions': subscriptions,
            'convert_to_mp3': convert_to_mp3,
            'downloaded_count': 0,
            'last_episode_times': {}  # 记录每个订阅的最后节目时间
        }
        
        with self.lock:
            self.tasks[task_id] = task
        
        return task_id
    
    def _execute_download_latest_task(self, task_id):
        """执行下载最新N集任务"""
        def run_task():
            with self.lock:
                if task_id not in self.tasks:
                    return
                task = self.tasks[task_id]
                task['status'] = 'running'
            
            try:
                for sub_idx, subscription in enumerate(task['subscriptions']):
                    rss_url = subscription.get('xmlUrl', '')
                    if not rss_url:
                        continue
                    
                    try:
                        episodes = get_episodes_from_rss(rss_url)
                        # 取最新的N集
                        latest_episodes = episodes[:task['count']]
                        
                        for episode in latest_episodes:
                            if episode.get('audio_url'):
                                success, file_id, file_path = self.download_manager.download_file(
                                    episode['audio_url'],
                                    episode_info=episode,
                                    username=task['username']
                                )
                                
                                # 如果需要转换且下载成功
                                if success and task.get('convert_to_mp3', False):
                                    self._convert_downloaded_file(file_id, file_path)
                                
                                with self.lock:
                                    task['results'].append({
                                        'episode': episode,
                                        'success': success,
                                        'file_id': file_id
                                    })
                                    if success:
                                        task['progress']['completed'] += 1
                                    else:
                                        task['progress']['failed'] += 1
                    except Exception as e:
                        print(f"处理订阅失败: {e}")
                        with self.lock:
                            task['progress']['failed'] += 1
                
                with self.lock:
                    task['status'] = 'completed'
            except Exception as e:
                with self.lock:
                    task['status'] = 'failed'
                    task['error'] = str(e)
        
        thread = threading.Thread(target=run_task, daemon=True)
        thread.start()
    
    def _check_monitor_tasks(self):
        """检查监听任务"""
        with self.lock:
            monitor_tasks = [t for t in self.tasks.values() if t['type'] == 'monitor' and t['status'] == 'running']
        
        for task in monitor_tasks:
            try:
                current_time = datetime.now().isoformat()
                
                for subscription in task['subscriptions']:
                    rss_url = subscription.get('xmlUrl', '')
                    if not rss_url:
                        continue
                    
                    sub_key = subscription.get('title', rss_url)
                    last_check_time = task['last_episode_times'].get(sub_key)
                    
                    # 检查更新
                    new_episodes = check_rss_update(rss_url, last_check_time)
                    
                    for episode in new_episodes:
                        if episode.get('audio_url'):
                            success, file_id, file_path = self.download_manager.download_file(
                                episode['audio_url'],
                                episode_info=episode,
                                username=task['username']
                            )
                            
                            if success:
                                # 如果需要转换
                                if task.get('convert_to_mp3', False):
                                    self._convert_downloaded_file(file_id, file_path)
                                
                                with self.lock:
                                    task['downloaded_count'] += 1
                                    if episode.get('published'):
                                        task['last_episode_times'][sub_key] = episode['published']
                
                with self.lock:
                    task['last_check'] = current_time
            except Exception as e:
                print(f"监听任务检查失败: {e}")
    
    def start_background_thread(self):
        """启动后台线程"""
        if self.running:
            return
        
        self.running = True
        
        def background_worker():
            while self.running:
                try:
                    self._check_monitor_tasks()
                except Exception as e:
                    print(f"后台任务执行失败: {e}")
                time.sleep(60)  # 每分钟检查一次
        
        self.thread = threading.Thread(target=background_worker, daemon=True)
        self.thread.start()
    
    def stop_background_thread(self):
        """停止后台线程"""
        self.running = False
    
    def get_task(self, task_id):
        """获取任务"""
        with self.lock:
            return self.tasks.get(task_id)
    
    def get_all_tasks(self):
        """获取所有任务"""
        with self.lock:
            return list(self.tasks.values())
    
    def cancel_task(self, task_id):
        """取消任务"""
        with self.lock:
            if task_id in self.tasks:
                task = self.tasks[task_id]
                if task['status'] in ['pending', 'running']:
                    task['status'] = 'cancelled'
                    return True
        return False
    
    def _convert_downloaded_file(self, file_id, file_path):
        """转换下载的文件为MP3并删除原文件"""
        try:
            if not file_path or not os.path.exists(file_path):
                logger.warning(f"文件不存在，无法转换: {file_path}")
                return
            
            audio_format = get_audio_format(file_path)
            
            # 如果已经是MP3，不需要转换
            if audio_format == 'mp3':
                logger.info(f"文件已经是MP3格式: {file_path}")
                return
            
            # 如果不是M4A，不转换
            if audio_format != 'm4a':
                logger.info(f"文件格式为{audio_format}，只转换M4A格式: {file_path}")
                return
            
            # 检查ffmpeg
            if not check_ffmpeg():
                logger.warning("ffmpeg未安装，无法转换格式")
                return
            
            # 生成输出路径
            base_name = os.path.splitext(file_path)[0]
            output_path = f"{base_name}.mp3"
            
            # 执行转换
            logger.info(f"开始转换音频文件 - 输入: {file_path}, 输出: {output_path}")
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
                file_info = self.download_manager.metadata.get(file_id)
                if file_info:
                    self.download_manager.metadata[file_id]['filename'] = new_filename
                    self.download_manager.metadata[file_id]['file_path'] = converted_path
                    self.download_manager.metadata[file_id]['size'] = os.path.getsize(converted_path)
                    self.download_manager.metadata[file_id]['downloaded_at'] = datetime.now().isoformat()
                    self.download_manager._save_metadata()
                    logger.info(f"音频转换成功并替换原文件 - 文件ID: {file_id}, 输出文件: {converted_path}")
                else:
                    logger.warning(f"未找到文件元数据: {file_id}")
            else:
                logger.error(f"音频转换失败 - 文件ID: {file_id}, 输入文件: {file_path}, 错误信息: {error}")
        except Exception as e:
            logger.exception(f"转换下载文件时发生异常 - 文件ID: {file_id}, 文件路径: {file_path}, 异常信息: {str(e)}")

