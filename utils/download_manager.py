"""
下载管理器
"""
import os
import requests
import hashlib
from datetime import datetime
import json
import re

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
    
    def _sanitize_filename(self, filename):
        """清理文件名，移除非法字符和emoji"""
        # 移除emoji和其他特殊符号（保留基本的中文、英文、数字和常用标点）
        # 只保留：中文、英文、数字、空格、-_()[]【】（）.!！
        filename = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9\s\-_\(\)\[\]【】（）.!！]', '', filename)
        # 移除Windows和Unix文件系统不允许的字符（再次确保）
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        # 移除控制字符
        filename = re.sub(r'[\x00-\x1f\x7f]', '', filename)
        # 将多个空格替换为单个空格
        filename = re.sub(r'\s+', ' ', filename)
        # 去除首尾空格和点
        filename = filename.strip('. ')
        # 限制长度（保留扩展名的空间）
        if len(filename) > 200:
            filename = filename[:200]
        return filename or 'episode'
    
    def _get_file_extension(self, url, content_type=None):
        """获取文件扩展名"""
        # 先尝试从URL获取
        url_path = url.split('?')[0]
        if url_path.endswith('.mp3'):
            return 'mp3'
        elif url_path.endswith('.m4a'):
            return 'm4a'
        elif url_path.endswith('.aac'):
            return 'aac'
        
        # 从Content-Type判断
        if content_type:
            if 'mp3' in content_type or 'mpeg' in content_type:
                return 'mp3'
            elif 'm4a' in content_type or 'mp4' in content_type:
                return 'm4a'
            elif 'aac' in content_type:
                return 'aac'
        
        # 默认返回mp3
        return 'mp3'
    
    def download_file(self, url, filename=None, episode_info=None, username=None):
        """
        下载文件
        返回: (success, file_id, file_path)
        """
        try:
            file_id = self._get_file_id(url)
            
            # 下载文件前先获取Content-Type
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, stream=True, timeout=30)
            response.raise_for_status()
            
            # 获取文件扩展名
            content_type = response.headers.get('Content-Type', '')
            file_ext = self._get_file_extension(url, content_type)
            
            # 确定文件名：优先使用节目标题
            if not filename:
                if episode_info and episode_info.get('title'):
                    # 使用节目标题作为文件名
                    base_name = self._sanitize_filename(episode_info['title'])
                    filename = f"{base_name}.{file_ext}"
                else:
                    # 尝试从URL中提取
                    url_filename = os.path.basename(url.split('?')[0])
                    if url_filename and '.' in url_filename:
                        filename = url_filename
                    else:
                        filename = f'{file_id}.{file_ext}'
            
            # 处理文件名冲突：如果同名文件已存在但是不同的URL，添加数字后缀
            original_filename = filename
            file_path = os.path.join(self.download_folder, filename)
            counter = 1
            
            while os.path.exists(file_path):
                # 检查是否是同一个文件（通过file_id）
                existing_file_id = None
                for fid, info in self.metadata.items():
                    if info.get('file_path') == file_path:
                        existing_file_id = fid
                        break
                
                if existing_file_id == file_id:
                    # 是同一个文件，直接返回
                    if file_id not in self.metadata:
                        self.metadata[file_id] = {
                            'url': url,
                            'filename': filename,
                            'file_path': file_path,
                            'downloaded_at': datetime.now().isoformat(),
                            'size': os.path.getsize(file_path),
                            'episode_info': episode_info or {},
                            'username': username or 'unknown'
                        }
                        self._save_metadata()
                    return True, file_id, file_path
                
                # 不是同一个文件，需要重命名
                base_name, ext = os.path.splitext(original_filename)
                filename = f"{base_name}_{counter}{ext}"
                file_path = os.path.join(self.download_folder, filename)
                counter += 1
            
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

