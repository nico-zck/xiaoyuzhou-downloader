"""
OPML文件解析器
"""
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup

def parse_opml(opml_content):
    """
    解析OPML内容
    返回订阅列表: [
        {
            'title': 标题,
            'text': 描述,
            'xmlUrl': RSS URL,
            'type': 类型
        },
        ...
    ]
    """
    subscriptions = []
    
    try:
        # 使用BeautifulSoup解析XML（更容错）
        soup = BeautifulSoup(opml_content, 'xml')
        
        # 查找所有outline元素
        outlines = soup.find_all('outline')
        
        for outline in outlines:
            # 检查是否是RSS订阅
            if outline.get('type') == 'rss' or outline.get('xmlUrl'):
                subscription = {
                    'title': outline.get('title', outline.get('text', '未知')),
                    'text': outline.get('text', ''),
                    'xmlUrl': outline.get('xmlUrl', ''),
                    'type': outline.get('type', 'rss')
                }
                subscriptions.append(subscription)
    except Exception as e:
        print(f"解析OPML失败: {e}")
        # 尝试使用ElementTree作为备选
        try:
            root = ET.fromstring(opml_content)
            for outline in root.findall('.//outline'):
                if outline.get('type') == 'rss' or outline.get('xmlUrl'):
                    subscription = {
                        'title': outline.get('title', outline.get('text', '未知')),
                        'text': outline.get('text', ''),
                        'xmlUrl': outline.get('xmlUrl', ''),
                        'type': outline.get('type', 'rss')
                    }
                    subscriptions.append(subscription)
        except Exception as e2:
            print(f"ElementTree解析也失败: {e2}")
    
    return subscriptions

