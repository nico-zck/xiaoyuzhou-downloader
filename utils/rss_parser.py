"""
RSS订阅解析器
"""
import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime

def parse_rss_feed(rss_url):
    """
    解析RSS订阅源
    返回feedparser对象
    """
    try:
        feed = feedparser.parse(rss_url)
        return feed
    except Exception as e:
        print(f"解析RSS失败: {e}")
        return None

def get_episodes_from_rss(rss_url):
    """
    从RSS源获取节目列表
    返回: [
        {
            'title': 标题,
            'description': 描述,
            'cover': 封面URL,
            'audio_url': 音频URL,
            'published': 发布时间,
            'link': 链接
        },
        ...
    ]
    """
    episodes = []
    
    # 首先尝试使用feedparser解析
    feed = parse_rss_feed(rss_url)
    
    if feed and feed.entries:
        for entry in feed.entries:
            episode = {
                'title': entry.get('title', '未知标题'),
                'description': entry.get('description', entry.get('summary', '')),
                'cover': '',
                'audio_url': '',
                'published': '',
                'link': entry.get('link', '')
            }
            
            # 提取发布时间
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                episode['published'] = datetime(*entry.published_parsed[:6]).isoformat()
            elif hasattr(entry, 'published'):
                episode['published'] = entry.published
            
            # 提取音频URL
            if hasattr(entry, 'enclosures') and entry.enclosures:
                for enclosure in entry.enclosures:
                    if enclosure.get('type', '').startswith('audio/'):
                        episode['audio_url'] = enclosure.get('href', '')
                        break
            
            # 如果没有找到enclosure，尝试从links中查找
            if not episode['audio_url'] and hasattr(entry, 'links'):
                for link in entry.links:
                    if link.get('type', '').startswith('audio/'):
                        episode['audio_url'] = link.get('href', '')
                        break
            
            # 提取封面图片
            if hasattr(entry, 'image'):
                episode['cover'] = entry.image.get('href', '')
            elif hasattr(entry, 'media_thumbnail'):
                episode['cover'] = entry.media_thumbnail[0].get('url', '')
            
            episodes.append(episode)
    else:
        # 如果feedparser失败，尝试直接请求并解析HTML（针对非标准RSS）
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(rss_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # 如果是HTML页面，尝试解析
            content_type = response.headers.get('Content-Type', '').lower()
            if 'text/html' in content_type or 'application/xhtml' in content_type:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # 尝试查找RSS链接
                rss_links = soup.find_all('link', type='application/rss+xml')
                if rss_links:
                    # 找到RSS链接，递归调用
                    for link in rss_links:
                        href = link.get('href', '')
                        if href:
                            # 处理相对URL
                            if not href.startswith('http'):
                                from urllib.parse import urljoin
                                href = urljoin(rss_url, href)
                            # 递归解析
                            return get_episodes_from_rss(href)
                
                # 尝试查找可能的播客列表
                # 查找包含音频链接的元素
                audio_links = soup.find_all('a', href=lambda x: x and any(ext in x.lower() for ext in ['.mp3', '.m4a', '.aac', 'audio']))
                for link in audio_links[:20]:  # 限制数量
                    episode = {
                        'title': link.get_text().strip() or '未知标题',
                        'description': '',
                        'cover': '',
                        'audio_url': link.get('href', ''),
                        'published': '',
                        'link': link.get('href', '')
                    }
                    # 处理相对URL
                    if episode['audio_url'] and not episode['audio_url'].startswith('http'):
                        from urllib.parse import urljoin
                        episode['audio_url'] = urljoin(rss_url, episode['audio_url'])
                        episode['link'] = episode['audio_url']
                    episodes.append(episode)
        except Exception as e:
            print(f"解析HTML页面失败: {e}")
    
    return episodes

def check_rss_update(rss_url, last_check_time=None):
    """
    检查RSS源是否有更新
    返回新节目列表
    """
    episodes = get_episodes_from_rss(rss_url)
    
    if last_check_time:
        # 过滤出发布时间在last_check_time之后的节目
        last_time = datetime.fromisoformat(last_check_time) if isinstance(last_check_time, str) else last_check_time
        new_episodes = []
        for episode in episodes:
            if episode['published']:
                pub_time = datetime.fromisoformat(episode['published']) if isinstance(episode['published'], str) else episode['published']
                if pub_time > last_time:
                    new_episodes.append(episode)
        return new_episodes
    
    return episodes

