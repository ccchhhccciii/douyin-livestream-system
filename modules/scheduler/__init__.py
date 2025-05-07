"""
调度器模块

包含音频队列和TTS生成队列的管理组件。
"""

import logging
logger = logging.getLogger(__name__)

# 导入需要的组件
from .tts_queue import TTSQueueManager
from .text_queue import TextQueue, Priority
from .tts import SimpleTTS
from .audio_player import AudioPlayer

logger.info("成功导入调度器组件")

__all__ = ['TTSQueueManager', 'TextQueue', 'Priority', 'SimpleTTS', 'AudioPlayer']
