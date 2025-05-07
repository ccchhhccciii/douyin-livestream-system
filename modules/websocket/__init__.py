"""
WebSocket模块，用于处理直播间消息通信和互动。

主要功能包括：
1. 通过WebSocket与直播服务器建立连接
2. 接收并解析各类消息（评论、礼物、关注等）
3. 处理直播互动信息
"""

from .websocket_client import WebSocketClient # Updated import
from .message_parser import MessageParser
# from .interaction_processor import InteractionProcessor # Temporarily commented out due to import error

__all__ = [
    'WebSocketClient',
    'MessageParser',
    # 'InteractionProcessor' # Temporarily commented out
]
