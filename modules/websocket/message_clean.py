"""
抖音电商无人直播系统 - WebSocket消息清理模块
负责根据业务规则过滤和清理WebSocket消息
"""

import logging
from typing import Dict, Any, Optional

class MessageCleaner:
    """
    负责根据业务规则清理WebSocket消息。
    目前主要用于过滤非评论消息，并提取评论内容。
    """

    def __init__(self):
        """初始化消息清理器"""
        self.logger = logging.getLogger(__name__)
        self.logger.info("MessageCleaner: __init__ completed.")

    def clean_message(self, processed_message: Dict[str, Any]) -> Optional[str]:
        """
        清理接收到的WebSocket消息。

        Args:
            processed_message: 经过解析后的消息字典。

        Returns:
            如果是评论消息，返回评论的文本内容；否则返回 None。
        """
        msg_type = processed_message.get('type')

        if msg_type == 'comment':
            self.logger.debug("MessageCleaner: Processing comment message.")
            try:
                # 提取评论内容
                content = processed_message.get('content', '无内容')
                self.logger.debug(f"MessageCleaner: Extracted comment content: {content[:50]}...")
                return content
            except Exception as e:
                self.logger.error(f"MessageCleaner: Error extracting comment content: {e}", exc_info=True)
                # 发生错误时返回 None
                return None
        else:
            self.logger.debug(f"MessageCleaner: Received non-comment message type '{msg_type}', ignoring.")
            # 非评论消息直接返回 None
            return None

# 示例用法 (仅用于测试或说明，实际应用中通过依赖注入或实例化使用)
if __name__ == "__main__":
    cleaner = MessageCleaner()

    # 模拟一个评论消息
    comment_msg = {
        'type': 'comment',
        'user': {'nickname': '测试用户'},
        'content': '这是一条测试评论内容！'
    }
    cleaned_comment = cleaner.clean_message(comment_msg)
    print(f"清理后的评论消息: {cleaned_comment}")

    # 模拟一个非评论消息 (例如用户进入直播间)
    user_enter_msg = {
        'type': 'user_enter',
        'user': {'nickname': '进入用户'},
        'count': 1
    }
    cleaned_user_enter = cleaner.clean_message(user_enter_msg)
    print(f"清理后的用户进入消息: {cleaned_user_enter}")
