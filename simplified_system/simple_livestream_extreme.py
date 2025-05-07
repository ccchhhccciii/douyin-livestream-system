"""
抖音电商无人直播系统 - 极简版核心实现

基于简化流程2.html的图示，直接实现核心功能流程：
SimpleAppUI -> WebSocketService -> LLM响应生成 -> TextQueue -> SimpleTTS -> AudioPlayer

极简化设计，专注核心功能链路，减少复杂度和线程管理
"""

import os
import sys
import logging
import time
import threading
import queue
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime

# 添加项目根目录到系统路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 导入核心组件
from modules.scheduler.text_queue import TextQueue, Priority
from modules.scheduler.tts import SimpleTTS
from modules.scheduler.audio_player import AudioPlayer
from modules.websocket.websocket_service import DouYinCommentService

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, QTimer, QThread


class ExtremeSimpleLivestreamSystem(QObject):
    """基于图示的极简直播系统实现
    
    直接连接核心组件：WebSocketService -> LLM -> TextQueue -> SimpleTTS -> AudioPlayer
    避免过度复杂的线程管理，专注于核心功能链路
    """
    # 定义信号
    system_status_changed = pyqtSignal(str, bool, str)  # 服务名称, 是否运行, 状态消息
    message_received = pyqtSignal(str)  # 收到的消息
    response_generated = pyqtSignal(str, dict)  # 生成的回复, 上下文信息
    log_message = pyqtSignal(str)  # 日志消息
    error_occurred = pyqtSignal(str, str)  # 错误类型, 错误消息
    
    def __init__(self):
        """初始化极简直播系统"""
        super().__init__()
        
        # 配置日志
        self._setup_logging()
        
        self.logger.info("初始化极简直播系统")
        
        # 系统状态
        self.running = False
        
        # 初始化组件
        self.text_queue = self._setup_text_queue()
        self.tts = self._setup_tts()
        self.audio_player = self._setup_audio_player()
        self.websocket_service = self._setup_websocket_service()
        
        # 连接信号和槽
        self._connect_signals_slots()
        
        self.logger.info("极简直播系统初始化完成")
    
    def _setup_logging(self):
        """设置日志"""
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # 确保有处理器
        if not self.logger.handlers:
            # 格式化器
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            
            # 控制台处理器
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            
            # 添加处理器
            self.logger.addHandler(console_handler)
            self.logger.setLevel(logging.INFO)
            
            # 创建日志目录
            log_dir = os.path.join(project_root, "data", "logs")
            os.makedirs(log_dir, exist_ok=True)
            
            # 文件处理器
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            log_file = os.path.join(log_dir, f"extreme_simple_{timestamp}.log")
            
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
            
            self.logger.info(f"日志已配置，文件: {log_file}")
    
    def _setup_text_queue(self) -> TextQueue:
        """设置文本队列
        
        Returns:
            文本队列实例
        """
        self.logger.info("初始化文本队列")
        text_queue = TextQueue()
        return text_queue
    
    def _setup_tts(self) -> SimpleTTS:
        """设置TTS引擎
        
        Returns:
            TTS引擎实例
        """
        self.logger.info("初始化TTS引擎")
        
        # 在项目根目录下创建音频输出目录
        audio_dir = os.path.join(project_root, 'data', 'audio')
        os.makedirs(audio_dir, exist_ok=True)
        
        tts = SimpleTTS(output_dir=audio_dir)
        return tts
    
    def _setup_audio_player(self) -> AudioPlayer:
        """设置音频播放器
        
        Returns:
            音频播放器实例
        """
        self.logger.info("初始化音频播放器")
        audio_player = AudioPlayer()
        return audio_player
    
    def _setup_websocket_service(self) -> DouYinCommentService:
        """设置WebSocket服务
        
        Returns:
            WebSocket服务实例
        """
        self.logger.info("初始化WebSocket服务")
        
        # WebSocket服务配置
        websocket_config = {
            "websocket_uri": "ws://127.0.0.1:8888",  # 默认地址
            "processor_config": {
                "filter_comments": False,  # 禁用过滤，确保所有消息都能通过
                "clean_nickname": False,   # 禁用昵称清理
                "allowed_message_types": [1]  # 只处理评论消息
            },
            "batch_size": 1  # 立即处理每条消息
        }
        
        # 创建WebSocket服务实例
        websocket_service = DouYinCommentService(websocket_config)
        
        # 设置WebSocket回调
        websocket_service.set_external_callback(self._handle_websocket_message)
        
        return websocket_service
    
    def _connect_signals_slots(self):
        """连接信号和槽"""
        self.logger.info("连接信号和槽")
        
        # 连接TTS信号
        self.tts.tts_started.connect(self._on_tts_started)
        self.tts.tts_completed.connect(self._on_tts_completed)
        self.tts.tts_failed.connect(self._on_tts_failed)
        
        # 连接文本队列信号
        self.text_queue.queue_updated.connect(self._on_queue_updated)
        self.text_queue.item_added.connect(self._on_item_added)
        self.text_queue.item_processing.connect(self._on_item_processing)
        self.text_queue.item_completed.connect(self._on_item_completed)
        
        # 连接音频播放器信号
        self.audio_player.playback_started.connect(self._on_playback_started)
        self.audio_player.playback_completed.connect(self._on_playback_completed)
        self.audio_player.playback_error.connect(self._on_playback_error)
    
    def _handle_websocket_message(self, message: str):
        """处理从WebSocket服务接收到的消息
        
        Args:
            message: 消息内容
        """
        try:
            # 记录日志
            self.logger.info(f"收到WebSocket消息: {message}")
            
            # 发出消息接收信号
            self.message_received.emit(message)
            
            # 生成LLM响应 - 极简实现，直接在方法中处理
            response = self._generate_llm_response(message)
            
            # 创建上下文信息
            context = {
                "event_type": "comment",
                "nickname": "用户",
                "message": message,
                "timestamp": time.time()
            }
            
            # 发出响应生成信号
            self.response_generated.emit(response, context)
            
            # 将响应添加到文本队列
            item_id = f"response_{int(time.time() * 1000)}"
            self.text_queue.add_text(response, item_id, Priority.HIGH)
            
        except Exception as e:
            self.logger.error(f"处理WebSocket消息时出错: {e}", exc_info=True)
            self.error_occurred.emit("消息处理错误", str(e))
    
    def _generate_llm_response(self, message: str) -> str:
        """生成LLM响应（极简实现）
        
        Args:
            message: 输入消息
        
        Returns:
            生成的回复
        """
        # 简单的响应映射
        responses = {
            "你好": "你好！欢迎来到我们的直播间",
            "价格": "这款产品的价格是99元，现在购买有优惠哦",
            "规格": "产品有多种规格可选，标准版、豪华版和专业版",
            "发货": "我们会在48小时内发货，支持全国配送",
            "优惠": "现在下单享受8折优惠，还有赠品相送",
            "质量": "我们的产品质量有保证，支持七天无理由退换",
        }
        
        # 检查消息是否包含关键词
        for key, value in responses.items():
            if key in message:
                return value
        
        # 默认回复
        return f"感谢您的消息：{message}。如果您对产品有任何疑问，请随时提问。"
    
    def _on_tts_started(self, item_id: str):
        """处理TTS开始事件
        
        Args:
            item_id: 项目ID
        """
        self.logger.debug(f"TTS开始处理: {item_id}")
    
    def _on_tts_completed(self, item_id: str, audio_path: str):
        """处理TTS完成事件
        
        Args:
            item_id: 项目ID
            audio_path: 音频文件路径
        """
        self.logger.info(f"TTS完成: {item_id}, 音频文件: {audio_path}")
        
        # 播放音频
        self.audio_player.play(audio_path, blocking=False)
    
    def _on_tts_failed(self, item_id: str, error_message: str):
        """处理TTS失败事件
        
        Args:
            item_id: 项目ID
            error_message: 错误消息
        """
        self.logger.error(f"TTS失败: {item_id}, 错误: {error_message}")
        self.error_occurred.emit("TTS错误", error_message)
    
    def _on_queue_updated(self, queue_size: int):
        """处理队列更新事件
        
        Args:
            queue_size: 队列大小
        """
        self.logger.debug(f"队列大小更新: {queue_size}")
    
    def _on_item_added(self, item_id: str, text: str, priority: int):
        """处理项目添加事件
        
        Args:
            item_id: 项目ID
            text: 文本内容
            priority: 优先级
        """
        self.logger.info(f"添加项目到队列: {item_id}, 优先级: {priority}")
    
    def _on_item_processing(self, item_id: str):
        """处理项目开始处理事件
        
        Args:
            item_id: 项目ID
        """
        self.logger.debug(f"开始处理项目: {item_id}")
        
        # 从文本队列获取到项目后，直接发送到TTS进行处理
        item = self.text_queue.get_next_item()
        if item:
            self.tts.synthesize(item['text'], item['id'])
    
    def _on_item_completed(self, item_id: str):
        """处理项目完成事件
        
        Args:
            item_id: 项目ID
        """
        self.logger.debug(f"项目处理完成: {item_id}")
    
    def _on_playback_started(self, audio_path: str):
        """处理音频播放开始事件
        
        Args:
            audio_path: 音频文件路径
        """
        self.logger.info(f"开始播放音频: {audio_path}")
    
    def _on_playback_completed(self, audio_path: str):
        """处理音频播放完成事件
        
        Args:
            audio_path: 音频文件路径
        """
        self.logger.info(f"音频播放完成: {audio_path}")
    
    def _on_playback_error(self, audio_path: str, error_message: str):
        """处理音频播放错误事件
        
        Args:
            audio_path: 音频文件路径
            error_message: 错误消息
        """
        self.logger.error(f"音频播放错误: {audio_path}, 错误: {error_message}")
        self.error_occurred.emit("音频播放错误", error_message)
    
    def start(self):
        """启动系统"""
        if self.running:
            self.logger.warning("系统已经在运行")
            return False
        
        self.logger.info("启动极简直播系统")
        
        try:
            # 启动文本队列
            self.text_queue.start()
            self.system_status_changed.emit("text_queue", True, "文本队列已启动")
            
            # 启动WebSocket服务
            ws_success = self.websocket_service.start()
            if not ws_success:
                self.logger.error("启动WebSocket服务失败")
                self.system_status_changed.emit("websocket", False, "启动失败")
                # 停止已启动的组件
                self.text_queue.stop()
                return False
            
            self.system_status_changed.emit("websocket", True, "WebSocket服务已启动")
            
            # 设置运行状态
            self.running = True
            self.log_message.emit("系统已启动")
            
            return True
            
        except Exception as e:
            self.logger.error(f"启动系统时出错: {e}", exc_info=True)
            self.error_occurred.emit("启动错误", str(e))
            self.stop()  # 确保停止所有已启动的组件
            return False
    
    def stop(self):
        """停止系统"""
        if not self.running:
            self.logger.warning("系统未在运行")
            return
        
        self.logger.info("停止极简直播系统")
        
        try:
            # 停止WebSocket服务
            if hasattr(self.websocket_service, 'running'):
                self.websocket_service.running = False
                
            # 停止WebSocket客户端
            if hasattr(self.websocket_service, 'websocket_client'):
                if hasattr(self.websocket_service.websocket_client, 'running'):
                    self.websocket_service.websocket_client.running = False
                
            self.system_status_changed.emit("websocket", False, "WebSocket服务已停止")
            
            # 停止文本队列
            self.text_queue.stop()
            self.system_status_changed.emit("text_queue", False, "文本队列已停止")
            
            # 停止音频播放
            self.audio_player.stop()
            
            # 清理资源
            self.audio_player.cleanup()
            self.tts.cleanup()
            
            # 设置运行状态
            self.running = False
            self.log_message.emit("系统已停止")
            
        except Exception as e:
            self.logger.error(f"停止系统时出错: {e}", exc_info=True)
            self.error_occurred.emit("停止错误", str(e))
    
    def add_custom_message(self, message: str):
        """添加自定义消息到系统
        
        Args:
            message: 消息内容
        """
        try:
            self.logger.info(f"添加自定义消息: {message}")
            
            # 直接处理消息，简化实现
            self._handle_websocket_message(message)
            
            return True
            
        except Exception as e:
            self.logger.error(f"添加自定义消息时出错: {e}", exc_info=True)
            self.error_occurred.emit("消息错误", str(e))
            return False
    
    def add_custom_script(self, script: str):
        """添加自定义话术到系统
        
        Args:
            script: 话术内容
        """
        try:
            self.logger.info(f"添加自定义话术: {script}")
            
            # 直接添加到文本队列
            item_id = f"script_{int(time.time())}"
            self.text_queue.add_text(script, item_id, Priority.NORMAL)
            
            return True
            
        except Exception as e:
            self.logger.error(f"添加自定义话术时出错: {e}", exc_info=True)
            self.error_occurred.emit("话术错误", str(e))
            return False
    
    def is_running(self) -> bool:
        """获取系统运行状态
        
        Returns:
            是否正在运行
        """
        return self.running
