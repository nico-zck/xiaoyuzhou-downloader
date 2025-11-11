"""
下载管理器
"""
import os
import requests
import hashlib
from datetime import datetime
import json

class DownloadManager:
    def __init__(self, download_folder='downloads'):
        self.download_folder = download_folder
        self.metadata_file = os.path.join(download_folder, 'metadata.json')
        os.makedirs(download_folder, exist_ok=True)
        self._load_metadata()
    
    def _load_metadata(self):
        """加载下载元数据"""
        if os.path.exists(self.metadata_file):
            with open(self.metadata_file, 'r', encoding='utf-8') as f:
                self.metadata = json.load(f)
        else:
            self.metadata = {}
    
    def _save_metadata(self):
        """保存下载元数据"""
        with open(self.metadata_file, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, ensure_ascii=False, indent=2)
    
    def _get_file_id(self, url):
        """生成文件ID"""
        return hashlib.md5(url.encode()).hexdigest()
    
    def download_file(self, url, filename=None, episode_info=None, username=None):
        """
        下载文件
        返回: (success, file_id, file_path)
        """
        try:
            file_id = self._get_file_id(url)
            
            # 如果没有提供文件名，从URL中提取
            if not filename:
                filename = os.path.basename(url.split('?')[0])
                if not filename or '.' not in filename:
                    filename = f'{file_id}.mp3'
            
            file_path = os.path.join(self.download_folder, filename)
            
            # 如果文件已存在，跳过下载
            if os.path.exists(file_path):
                return True, file_id, file_path
            
            # 下载文件
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, stream=True, timeout=30)
            response.raise_for_status()
            
            # 保存文件
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # 保存元数据
            self.metadata[file_id] = {
                'url': url,
                'filename': filename,
                'file_path': file_path,
                'downloaded_at': datetime.now().isoformat(),
                'size': os.path.getsize(file_path),
                'episode_info': episode_info or {},
                'username': username or 'unknown'  # 添加用户信息
            }
            self._save_metadata()
            
            return True, file_id, file_path
        except Exception as e:
            print(f"下载失败: {e}")
            return False, None, None
    
    def list_downloads(self, username=None):
        """
        列出已下载的文件
        username: 可选，如果提供则只返回该用户的下载
        """
        downloads = []
        for file_id, info in self.metadata.items():
            if os.path.exists(info['file_path']):
                # 如果指定了用户名，只返回该用户的下载
                if username and info.get('username') != username:
                    continue
                downloads.append({
                    'file_id': file_id,
                    **info
                })
        # 按下载时间倒序排列
        downloads.sort(key=lambda x: x.get('downloaded_at', ''), reverse=True)
        return downloads
    
    def delete_file(self, file_id):
        """删除文件"""
        if file_id in self.metadata:
            info = self.metadata[file_id]
            file_path = info['file_path']
            
            # 删除文件
            if os.path.exists(file_path):
                os.remove(file_path)
            
            # 删除元数据
            del self.metadata[file_id]
            self._save_metadata()
            
            return True
        return False
    
    def delete_files_batch(self, file_ids):
        """
        批量删除文件
        返回: (成功数量, 失败的文件ID列表)
        """
        success_count = 0
        failed_ids = []
        
        for file_id in file_ids:
            if self.delete_file(file_id):
                success_count += 1
            else:
                failed_ids.append(file_id)
        
        return success_count, failed_ids
    
    def get_users(self):
        """获取所有用户列表"""
        users = set()
        for info in self.metadata.values():
            username = info.get('username', 'unknown')
            users.add(username)
        return sorted(list(users))

