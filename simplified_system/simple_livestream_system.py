"""
抖音电商无人直播系统 - 简化版核心
集成WebSocketService、TextQueue、SimpleTTS和AudioPlayer的极简实现
解决线程阻塞问题，确保UI响应性
"""

import os
import sys
import logging
import time
import threading
import queue
from typing import Dict, Any, Optional, List, Callable

# 使用自定义StreamHandler处理Unicode字符
class UnicodeStreamHandler(logging.StreamHandler):
    """支持Unicode字符的StreamHandler"""
    def __init__(self, stream=None):
        super().__init__(stream)
        self.encoding = 'utf-8'
        
    def emit(self, record):
        try:
            msg = self.format(record)
            stream = self.stream
            # 在Windows上，强制使用sys.stdout设置为UTF-8模式输出
            if os.name == 'nt':
                try:
                    stream.write(msg + self.terminator)
                except UnicodeEncodeError:
                    # 如果出现编码错误，替换无法显示的字符
                    cleaned_msg = ''.join(c if ord(c) < 0x10000 else '?' for c in msg)
                    stream.write(cleaned_msg + self.terminator)
            else:
                stream.write(msg + self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)

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


class LLMResponseWorker(QObject):
    """LLM响应生成线程工作器"""
    response_generated = pyqtSignal(str, str, dict)  # 输入消息, 生成的回复, 上下文信息
    finished = pyqtSignal()
    error = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.message_queue = queue.Queue()
        self.running = False
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # 确保日志处理器能处理Unicode字符
        if not self.logger.handlers:
            handler = UnicodeStreamHandler()
            handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
    
    @pyqtSlot()
    def process(self):
        """处理消息队列，生成LLM响应"""
        self.running = True
        self.logger.info("LLM响应生成线程已启动")
        
        while self.running:
            try:
                # 非阻塞方式获取消息，避免线程卡死
                try:
                    message = self.message_queue.get(block=True, timeout=0.5)
                except queue.Empty:
                    continue
                
                # 生成响应
                self.logger.info(f"处理消息: {message}")
                
                # 简单的响应生成逻辑，实际项目中会调用真实的LLM
                response = self._generate_response(message)
                
                # 创建上下文信息
                context = {
                    "event_type": "comment",
                    "nickname": "用户",
                    "message": message,
                    "timestamp": time.time()
                }
                
                # 发出响应生成信号
                self.response_generated.emit(message, response, context)
                
                # 标记任务完成
                self.message_queue.task_done()
                
            except Exception as e:
                self.logger.error(f"生成LLM响应时出错: {e}", exc_info=True)
                self.error.emit(f"生成LLM响应时出错: {e}")
        
        self.logger.info("LLM响应生成线程已停止")
        self.finished.emit()
    
    def add_message(self, message: str):
        """添加消息到队列
        
        Args:
            message: 消息内容
        """
        self.message_queue.put(message)
        self.logger.debug(f"添加消息到LLM处理队列: {message}")
    
    def stop(self):
        """停止处理"""
        self.running = False
        self.logger.info("请求停止LLM响应生成线程")
    
    def _generate_response(self, message: str) -> str:
        """生成LLM响应（简化版-模拟）
        
        Args:
            message: 输入消息
        
        Returns:
            生成的回复
        """
        # 模拟处理延迟，但不会太长阻塞UI
        time.sleep(0.1)
        
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


class SimpleStreamSystem(QObject):
    """简化版直播系统核心
    
    集成WebSocketService、TextQueue、SimpleTTS和AudioPlayer组件，
    实现从WebSocket消息接收到语音播放的完整流程
    """
    # 定义信号
    system_status_changed = pyqtSignal(str, bool, str)  # 服务名称, 是否运行, 状态消息
    message_received = pyqtSignal(str)  # 收到的消息
    response_generated = pyqtSignal(str, dict)  # 生成的回复, 上下文信息
    log_message = pyqtSignal(str)  # 日志消息
    error_occurred = pyqtSignal(str, str)  # 错误类型, 错误消息
    
    def __init__(self):
        """初始化简化版直播系统"""
        super().__init__()
        
        # 配置日志
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # 确保日志处理器能处理Unicode字符
        if not self.logger.handlers:
            handler = UnicodeStreamHandler()
            handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
        
        self.logger.info("初始化简化版直播系统")
        
        # 初始化线程
        self._setup_threads()
        
        # 初始化组件
        self.text_queue = self._setup_text_queue()
        self.tts = self._setup_tts()
        self.audio_player = self._setup_audio_player()
        self.websocket_service = self._setup_websocket_service()
        
        # 连接信号和槽
        self._connect_signals_slots()
        
        # 系统状态
        self.running = False
        
        # 创建处理定时器 - 避免直接在信号处理函数中进行耗时操作
        self.process_timer = QTimer(self)
        self.process_timer.timeout.connect(self._process_queue_item)
        self.process_timer.setInterval(100)  # 100毫秒间隔
        
        self.logger.info("简化版直播系统初始化完成")
    
    def _setup_threads(self):
        """设置工作线程"""
        self.logger.info("初始化工作线程")
        
        # LLM响应生成线程
        self.llm_thread = QThread()
        self.llm_worker = LLMResponseWorker()
        self.llm_worker.moveToThread(self.llm_thread)
        
        # 连接线程信号
        self.llm_thread.started.connect(self.llm_worker.process)
        self.llm_worker.finished.connect(self.llm_thread.quit)
        self.llm_worker.response_generated.connect(self._on_llm_response_generated)
        self.llm_worker.error.connect(lambda msg: self.error_occurred.emit("LLM错误", msg))
        
        # 启动线程
        self.llm_thread.start()
    
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
        self.logger.info("创建WebSocket服务实例")
        websocket_service = DouYinCommentService(websocket_config)
        
        # 设置WebSocket回调，通过QTimer将回调移到主线程处理
        self.logger.info("设置WebSocket服务回调函数")
        websocket_service.set_external_callback(self._handle_websocket_message_with_timer)
        
        return websocket_service
    
    def _handle_websocket_message_with_timer(self, message: str):
        """使用定时器代理处理WebSocket消息，防止线程阻塞
        
        Args:
            message: 消息内容
        """
        # 使用QTimer.singleShot将消息处理转移到主线程，避免WebSocket线程阻塞
        QTimer.singleShot(0, lambda: self._handle_websocket_message(message))
    
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
        """处理从WebSocket服务接收到的消息（在主线程中执行）
        
        Args:
            message: 消息内容
        """
        try:
            # 记录日志
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            self.logger.info(f"[{timestamp}] 收到WebSocket消息: {message}")
            
            # 发出消息接收信号
            self.message_received.emit(message)
            
            # 将消息添加到LLM响应生成队列（非阻塞）
            self.llm_worker.add_message(message)
            
        except Exception as e:
            self.logger.error(f"处理WebSocket消息时出错: {e}", exc_info=True)
            self.error_occurred.emit("消息处理错误", str(e))
    
    @pyqtSlot(str, str, dict)
    def _on_llm_response_generated(self, message: str, response: str, context: dict):
        """处理LLM生成的响应（从LLM线程接收到主线程）
        
        Args:
            message: 原始消息
            response: 生成的回复
            context: 上下文信息
        """
        try:
            self.logger.info(f"接收到LLM响应: {response}")
            
            # 发出响应生成信号
            self.response_generated.emit(response, context)
            
            # 将响应添加到文本队列 - 使用QTimer避免文本队列处理阻塞UI
            QTimer.singleShot(0, lambda: self._add_response_to_queue(response))
            
        except Exception as e:
            self.logger.error(f"处理LLM响应时出错: {e}", exc_info=True)
            self.error_occurred.emit("响应处理错误", str(e))
    
    def _add_response_to_queue(self, response: str):
        """将响应添加到文本队列
        
        Args:
            response: 响应文本
        """
        try:
            # 创建ID并添加到队列
            item_id = f"response_{int(time.time() * 1000)}"
            self.text_queue.add_text(response, item_id, Priority.HIGH)
            self.logger.debug(f"添加响应到文本队列: {item_id}")
            
        except Exception as e:
            self.logger.error(f"添加响应到队列时出错: {e}", exc_info=True)
            self.error_occurred.emit("队列处理错误", str(e))
    
    def _process_queue_item(self):
        """定时处理队列中的项目"""
        if not self.running:
            return
            
        try:
            # 从队列中获取下一个项目
            item = self.text_queue.get_next_item()
            if not item:
                return
            
            # 发送到TTS引擎 - TTS内部有线程保护，不会阻塞UI
            self.tts.synthesize(item['text'], item['id'])
            
        except Exception as e:
            self.logger.error(f"处理队列项目时出错: {e}", exc_info=True)
            self.error_occurred.emit("队列处理错误", str(e))
    
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
        
        # 使用QTimer触发播放，避免UI阻塞
        QTimer.singleShot(0, lambda: self.audio_player.play(audio_path, blocking=False))
    
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
        
        # 确保处理定时器运行中
        if not self.process_timer.isActive() and self.running:
            self.process_timer.start()
    
    def _on_item_processing(self, item_id: str):
        """处理项目开始处理事件
        
        Args:
            item_id: 项目ID
        """
        self.logger.debug(f"开始处理项目: {item_id}")
    
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
        
        self.logger.info("启动简化版直播系统")
        
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
            
            # 启动处理定时器
            self.process_timer.start()
            
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
        
        self.logger.info("停止简化版直播系统")
        
        try:
            # 停止处理定时器
            if self.process_timer.isActive():
                self.process_timer.stop()
            
            # 停止WebSocket服务
            if hasattr(self.websocket_service, 'running'):
                self.websocket_service.running = False
                
            # 停止WebSocket客户端
            if hasattr(self.websocket_service, 'websocket_client'):
                if hasattr(self.websocket_service.websocket_client, 'running'):
                    self.websocket_service.websocket_client.running = False
                
            self.system_status_changed.emit("websocket", False, "WebSocket服务已停止")
            
            # 停止LLM响应生成线程
            if hasattr(self, 'llm_worker'):
                self.llm_worker.stop()
            
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
            
            # 使用QTimer触发消息处理，避免UI阻塞
            QTimer.singleShot(0, lambda: self._handle_websocket_message(message))
            
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
            
            # 使用QTimer触发话术添加，避免UI阻塞
            item_id = f"script_{int(time.time())}"
            QTimer.singleShot(0, lambda: self.text_queue.add_text(script, item_id, Priority.NORMAL))
            
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
