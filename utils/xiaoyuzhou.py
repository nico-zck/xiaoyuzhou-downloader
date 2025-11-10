"""
小宇宙播客链接解析和下载功能
参考: https://github.com/LGiki/cosmos-enhanced
"""
import re
import requests
from bs4 import BeautifulSoup

def extract_episode_id(url):
    """从小宇宙链接中提取episode ID"""
    match = re.search(r'/episode/([a-f0-9]+)', url)
    if match:
        return match.group(1)
    return None

def get_episode_info(episode_url):
    """
    获取单集节目信息
    返回: {
        'title': 标题,
        'description': 描述,
        'cover': 封面URL,
        'audio_url': 音频URL
    }
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(episode_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 提取标题
        title_elem = soup.find('h1') or soup.find('title')
        title = title_elem.get_text().strip() if title_elem else '未知标题'
        
        # 提取描述
        description = ''
        desc_elem = soup.find('meta', property='og:description') or soup.find('meta', attrs={'name': 'description'})
        if desc_elem:
            description = desc_elem.get('content', '')
        
        # 提取封面
        cover = ''
        cover_elem = soup.find('meta', property='og:image')
        if cover_elem:
            cover = cover_elem.get('content', '')
        
        # 尝试从页面中提取音频URL
        # 小宇宙的音频URL通常在JavaScript中或通过API获取
        audio_url = None
        
        # 方法1: 从script标签中查找JSON数据
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string:
                # 查找包含episode数据的JSON
                json_match = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.+?});', script.string, re.DOTALL)
                if json_match:
                    try:
                        import json
                        data = json.loads(json_match.group(1))
                        # 尝试多种可能的路径
                        if 'episode' in data:
                            episode_data = data['episode']
                            if 'enclosure' in episode_data:
                                audio_url = episode_data['enclosure'].get('url', '')
                            elif 'audioUrl' in episode_data:
                                audio_url = episode_data['audioUrl']
                            elif 'mediaUrl' in episode_data:
                                audio_url = episode_data['mediaUrl']
                    except:
                        pass
                
                # 如果还没找到，查找直接的音频URL模式
                if not audio_url:
                    audio_match = re.search(r'["\'](https?://[^"\']*\.(mp3|m4a|aac|m3u8)[^"\']*)["\']', script.string)
                    if audio_match:
                        audio_url = audio_match.group(1)
                        break
        
        # 方法2: 通过episode ID调用API
        episode_id = extract_episode_id(episode_url)
        if episode_id and not audio_url:
            # 尝试多种API端点
            api_endpoints = [
                f'https://www.xiaoyuzhoufm.com/api/v1/episode/{episode_id}',
                f'https://api.xiaoyuzhoufm.com/v1/episode/{episode_id}',
                f'https://www.xiaoyuzhoufm.com/api/episode/{episode_id}',
            ]
            
            for api_url in api_endpoints:
                try:
                    api_response = requests.get(api_url, headers=headers, timeout=10)
                    if api_response.status_code == 200:
                        api_data = api_response.json()
                        # 尝试多种可能的字段路径
                        if 'data' in api_data:
                            data = api_data['data']
                            if 'enclosure' in data:
                                audio_url = data['enclosure'].get('url', '')
                            elif 'audioUrl' in data:
                                audio_url = data['audioUrl']
                            elif 'mediaUrl' in data:
                                audio_url = data['mediaUrl']
                            elif 'audio' in data:
                                audio_url = data['audio'].get('url', '') if isinstance(data['audio'], dict) else data['audio']
                        
                        if audio_url:
                            break
                except Exception as e:
                    continue
        
        return {
            'title': title,
            'description': description,
            'cover': cover,
            'audio_url': audio_url,
            'episode_id': episode_id
        }
    except Exception as e:
        print(f"获取节目信息失败: {e}")
        return None

def get_download_url(episode_url):
    """
    获取音频下载链接
    返回下载URL字符串
    """
    info = get_episode_info(episode_url)
    if info and info.get('audio_url'):
        return info['audio_url']
    
    # 如果无法从页面获取，尝试通过episode ID构造API请求
    episode_id = extract_episode_id(episode_url)
    if episode_id:
        # 尝试多种可能的API端点
        api_endpoints = [
            f'https://www.xiaoyuzhoufm.com/api/v1/episode/{episode_id}',
            f'https://api.xiaoyuzhoufm.com/v1/episode/{episode_id}',
        ]
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        for api_url in api_endpoints:
            try:
                response = requests.get(api_url, headers=headers, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    # 尝试多种可能的字段路径
                    audio_url = None
                    if 'data' in data:
                        if 'enclosure' in data['data']:
                            audio_url = data['data']['enclosure'].get('url', '')
                        elif 'audio' in data['data']:
                            audio_url = data['data']['audio'].get('url', '')
                        elif 'media' in data['data']:
                            audio_url = data['data']['media'].get('url', '')
                    
                    if audio_url:
                        return audio_url
            except:
                continue
    
    return None

