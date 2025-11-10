"""
任务管理器
"""
import threading
import time
import uuid
from datetime import datetime
from utils.rss_parser import get_episodes_from_rss, check_rss_update
from utils.download_manager import DownloadManager

class TaskManager:
    def __init__(self, download_manager):
        self.download_manager = download_manager
        self.tasks = {}
        self.running = False
        self.thread = None
        self.lock = threading.Lock()
    
    def create_download_latest_task(self, username, subscriptions, count):
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
            'progress': {
                'total': len(subscriptions),
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
    
    def create_monitor_task(self, username, subscriptions):
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
                                    episode_info=episode
                                )
                                
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
                        task['progress']['completed'] += 1
                
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
                                episode_info=episode
                            )
                            
                            if success:
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

