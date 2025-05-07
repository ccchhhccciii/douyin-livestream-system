"""
文本队列模块 - 管理需要处理的TTS文本
提供队列管理、优先级处理等功能
"""

import time
import queue
import threading
import logging
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple
from PyQt6.QtCore import QObject, pyqtSignal


class Priority(Enum):
    """文本处理优先级"""
    HIGH = 1    # 高优先级(用户互动回复)
    NORMAL = 2  # 普通优先级(常规话术)
    LOW = 3     # 低优先级(背景话术)


class TextQueue(QObject):
    """文本队列管理器"""
    # 定义信号
    queue_updated = pyqtSignal(int)  # 队列更新信号(队列大小)
    item_added = pyqtSignal(str, str, int)  # 项目添加信号(项目ID, 文本, 优先级)
    item_processing = pyqtSignal(str)  # 项目开始处理信号(项目ID)
    item_completed = pyqtSignal(str)  # 项目完成信号(项目ID)
    
    def __init__(self):
        """初始化文本队列"""
        super().__init__()
        # 创建优先级队列
        self.text_queue = queue.PriorityQueue()
        # 当前队列大小
        self.queue_size = 0
        # 运行标志
        self.running = False
        # 队列处理线程
        self.thread = None
        # 线程锁
        self.lock = threading.Lock()
        # 配置日志
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info("文本队列初始化完成")
    
    def start(self):
        """启动队列处理"""
        with self.lock:
            if self.running:
                self.logger.warning("文本队列处理已在运行")
                return
            
            self.running = True
            self.thread = threading.Thread(target=self._process_queue, daemon=True)
            self.thread.start()
            self.logger.info("文本队列处理线程已启动")
    
    def stop(self):
        """停止队列处理"""
        with self.lock:
            if not self.running:
                self.logger.warning("文本队列处理未在运行")
                return
            
            self.running = False
            if self.thread and self.thread.is_alive():
                self.thread.join(2.0)  # 等待最多2秒
            self.logger.info("文本队列处理线程已停止")
    
    def add_text(self, text: str, item_id: str, priority: Priority = Priority.NORMAL, 
                 metadata: Optional[Dict[str, Any]] = None):
        """添加文本到队列
        
        Args:
            text: 要处理的文本
            item_id: 文本唯一ID
            priority: 处理优先级
            metadata: 元数据字典
        """
        if not text or not text.strip():
            self.logger.warning(f"尝试添加空文本，已忽略: {item_id}")
            return
        
        if metadata is None:
            metadata = {}
        
        # 创建队列项
        queue_item = {
            'id': item_id,
            'text': text,
            'priority': priority,
            'metadata': metadata,
            'timestamp': time.time()
        }
        
        # 添加到队列
        # 元组第一项是优先级值，用于排序；第二项是时间戳，确保同优先级时FIFO；第三项是实际数据
        self.text_queue.put((priority.value, queue_item['timestamp'], queue_item))
        
        with self.lock:
            self.queue_size += 1
        
        # 发送信号
        self.queue_updated.emit(self.queue_size)
        self.item_added.emit(item_id, text, priority.value)
        
        self.logger.info(f"添加文本到队列: ID={item_id}, 优先级={priority.name}, 队列大小={self.queue_size}")
    
    def get_next_item(self) -> Optional[Dict[str, Any]]:
        """获取下一个待处理项目
        
        Returns:
            下一个待处理的队列项，或者None如果队列为空
        """
        try:
            if self.text_queue.empty():
                return None
            
            # 获取下一个项目
            _, _, item = self.text_queue.get(block=False)
            
            with self.lock:
                self.queue_size -= 1
            
            # 发送信号
            self.queue_updated.emit(self.queue_size)
            
            self.logger.debug(f"获取下一个队列项: ID={item['id']}, 队列剩余={self.queue_size}")
            return item
        except queue.Empty:
            return None
        except Exception as e:
            self.logger.error(f"获取下一个队列项时出错: {e}", exc_info=True)
            return None
    
    def clear(self):
        """清空队列"""
        # 创建一个新队列替换现有队列
        with self.lock:
            self.text_queue = queue.PriorityQueue()
            old_size = self.queue_size
            self.queue_size = 0
        
        # 发送信号
        self.queue_updated.emit(0)
        
        self.logger.info(f"清空队列，移除了{old_size}个项目")
    
    def get_queue_size(self) -> int:
        """获取当前队列大小
        
        Returns:
            队列中的项目数量
        """
        with self.lock:
            return self.queue_size
    
    def _process_queue(self):
        """队列处理线程的主方法"""
        self.logger.info("队列处理线程开始运行")
        
        while self.running:
            try:
                # 处理队列中的下一个项目
                item = self.get_next_item()
                if item:
                    # 发出正在处理信号
                    self.item_processing.emit(item['id'])
                    
                    # 实际处理应该由外部组件完成
                    # 这里只是简单地等待一小段时间来模拟处理
                    time.sleep(0.05)
                    
                    # 发出完成信号
                    self.item_completed.emit(item['id'])
                else:
                    # 队列为空，休眠一段时间
                    time.sleep(0.1)
            except Exception as e:
                self.logger.error(f"队列处理线程出错: {e}", exc_info=True)
                time.sleep(1.0)  # 出错后休眠较长时间
        
        self.logger.info("队列处理线程已结束")
