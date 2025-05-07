"""
WebSocket客户端模块，负责与直播服务器建立连接并接收消息。

重构：移除内部线程和Asyncio事件循环，直接在PyQt工作线程中运行异步逻辑。
"""

import asyncio
import logging
import websockets
import json
import random # Added random for simulation
import time # Added time for simulation
# Removed threading
from typing import Dict, Any, Optional, Callable, List

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, QTimer, QMutex, QMutexLocker

# Import necessary components for asyncio integration with PyQt using qasync
from qasync import QEventLoop, asyncSlot, asyncClose

from .message_parser import MessageParser
from .message_clean import MessageCleaner # Import MessageCleaner

class WebSocketClient(QObject): # Inherit from QObject to use signals/slots
    """WebSocket客户端，用于连接到消息源并获取直播间消息"""

    # Define signals to communicate with the worker thread
    _connection_attempt_signal = pyqtSignal()
    _message_received_internal = pyqtSignal(str) # Signal to pass raw message to slot in worker thread
    connection_status_changed = pyqtSignal(bool, str) # Signal to indicate connection status change
    error_occurred = pyqtSignal(str, str) # Signal to indicate an error occurred
    log_message = pyqtSignal(str) # Signal to emit log messages

    def __init__(self,
                 websocket_uri: str = "ws://127.0.0.1:8888",  # 修改为抖音直播服务器的默认地址
                 processor_config: Optional[Dict[str, Any]] = None,
                 message_callback: Optional[Callable[[str], None]] = None): # Updated type hint
        """
        初始化WebSocket客户端

        Args:
            websocket_uri: WebSocket服务器URI
            processor_config: 消息解析器配置
            message_callback: 当收到并清理后的评论内容时的回调函数 (str)
        """
        super().__init__() # Initialize QObject
        self.logger = logging.getLogger(__name__)
        log_msg = "WebSocketClient: __init__ called."
        self.logger.info(log_msg)
        self.log_message.emit(log_msg) # Emit log signal

        self.websocket_uri = websocket_uri
        self.processor = MessageParser(config=processor_config)
        self.cleaner = MessageCleaner() # Instantiate MessageCleaner
        
        # 修改为支持多个回调函数
        self.message_callbacks = []
        if message_callback:
            self.message_callbacks.append(message_callback)

        # Connection state and control
        self.running = False
        self.connected = False
        self._stop_requested = False

        self.reconnect_interval = 5  # Reconnect interval (seconds)
        self.max_reconnect_attempts = 10  # Max reconnect attempts

        # Current WebSocket connection and receive task
        self.websocket = None
        self._receive_task = None

        # Stats
        self.stats = {
            "messages_received": 0,
            "messages_processed": 0,
            "messages_filtered": 0,
            "connection_errors": 0,
            "reconnect_attempts": 0,
            "processing_errors": 0
        }

        # Timer for scheduling connection attempts
        self._connection_timer = QTimer()
        self._connection_timer.timeout.connect(self._attempt_connect)

        # Connect internal signals
        self._connection_attempt_signal.connect(self._attempt_connect)
        # _message_received_internal is emitted from async task and connected to sync slot
        self._message_received_internal.connect(self._process_raw_message)


        log_msg = "WebSocketClient: __init__ completed."
        self.logger.info(log_msg)
        self.log_message.emit(log_msg) # Emit log signal

    @pyqtSlot()
    def start(self):
        """Start the WebSocket client (initiate connection attempt)"""
        if self.running:
            log_msg = "WebSocket客户端已经在运行"
            self.logger.warning(log_msg)
            self.log_message.emit(log_msg) # Emit log signal
            return False

        self.running = True
        self._stop_requested = False
        self.stats["reconnect_attempts"] = 0 # Reset reconnect attempts on explicit start

        log_msg = f"WebSocket客户端启动中，尝试连接到 {self.websocket_uri}"
        self.logger.info(log_msg)
        self.log_message.emit(log_msg) # Emit log signal
        # Emit signal to start the connection attempt in the worker thread
        self._connection_attempt_signal.emit()
        return True

    @asyncSlot() # Use asyncSlot for async method connected to a signal
    async def stop(self):
        """停止WebSocket客户端"""
        if not self.running:
            log_msg = "WebSocket客户端未在运行"
            self.logger.warning(log_msg)
            self.log_message.emit(log_msg)
            return

        self.running = False
        self._stop_requested = True

        # 停止连接定时器
        if self._connection_timer.isActive():
            self._connection_timer.stop()

        # Cancel the receive task
        if self._receive_task and not self._receive_task.done():
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                log_msg = "WebSocketClient: Receive task cancelled."
                self.logger.info(log_msg)
                self.log_message.emit(log_msg)
            except Exception as e:
                 error_msg = f"WebSocketClient: Error cancelling receive task: {e}"
                 self.logger.error(error_msg)
                 self.log_message.emit(error_msg)
                 self.error_occurred.emit("清理错误", error_msg)


        # Close WebSocket connection asynchronously
        if self.websocket:
            try:
                await self.websocket.close()
                self.websocket = None
                self.connected = False

                log_msg = "WebSocketClient: 连接已关闭"
                self.logger.info(log_msg)
                self.log_message.emit(log_msg)
                self.connection_status_changed.emit(False, "已断开")

            except Exception as e:
                error_msg = f"WebSocketClient: 关闭连接时出错: {e}"
                self.logger.error(error_msg)
                self.log_message.emit(error_msg)
                self.error_occurred.emit("清理错误", f"关闭WebSocket连接时出错: {e}")

        log_msg = "已停止WebSocket客户端"
        self.logger.info(log_msg)
        self.log_message.emit(log_msg)


    @asyncSlot() # Use asyncSlot for async method connected to a signal
    async def _attempt_connect(self):
        """尝试连接到WebSocket服务器"""
        if not self.running or self._stop_requested:
            log_msg = "WebSocketClient: 连接尝试已中止（未运行或请求停止）"
            self.logger.info(log_msg)
            self.log_message.emit(log_msg)
            return

        if self.connected:
            log_msg = "WebSocketClient: 已经连接，跳过连接尝试"
            self.logger.info(log_msg)
            self.log_message.emit(log_msg)
            return

        self.stats["reconnect_attempts"] += 1
        log_msg = f"WebSocketClient: 尝试连接到WebSocket服务器: {self.websocket_uri} (尝试 {self.stats['reconnect_attempts']})"
        self.logger.info(log_msg)
        self.log_message.emit(log_msg)

        try:
            self.logger.debug(f"WebSocketClient: _attempt_connect - 开始连接 {self.websocket_uri}")
            # 设置连接超时
            timeout = 5  # 5秒超时
            connection_task = self._connect()
            
            # 使用asyncio.wait_for实现超时控制
            try:
                await asyncio.wait_for(connection_task, timeout)
                # 如果连接成功，不会运行到这里，因为_connect会设置self.connected
                if not self.connected:
                    self.logger.warning("WebSocketClient: 连接未成功建立但未出现异常")
            except asyncio.TimeoutError:
                # 连接超时
                self.stats["connection_errors"] += 1
                error_msg = f"WebSocketClient: 连接到 {self.websocket_uri} 超时 ({timeout}秒)"
                self.logger.error(error_msg)
                self.error_occurred.emit("连接超时", error_msg)
                
                # 更新连接状态
                self.connected = False
                self.connection_status_changed.emit(False, "连接超时")
                self.log_message.emit(error_msg)
                
                # 检查是否需要重试
                if self.stats["reconnect_attempts"] < self.max_reconnect_attempts:
                    self.logger.info(f"WebSocketClient: 将在 {self.reconnect_interval} 秒后重试连接")
                    self.log_message.emit(f"将在 {self.reconnect_interval} 秒后重试连接")
                    await asyncio.sleep(self.reconnect_interval)
                    asyncio.create_task(self._attempt_connect()) # 重试连接
                else:
                    error_msg = f"WebSocketClient: 已达到最大重连尝试次数 ({self.max_reconnect_attempts})"
                    self.logger.error(error_msg)
                    self.error_occurred.emit("最大重连次数", error_msg)
                    self.log_message.emit(error_msg)
                    
                    # 确保UI状态更新为已停止
                    self.connection_status_changed.emit(False, "已达到最大重试次数")
            
        except Exception as e:
            self.stats["connection_errors"] += 1
            error_msg = f"WebSocketClient: 连接尝试出错: {type(e).__name__}: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            self.error_occurred.emit(type(e).__name__, str(e))
            
            # 更新连接状态
            self.connected = False
            self.connection_status_changed.emit(False, f"连接失败: {str(e)}")
            self.log_message.emit(error_msg)
            
            # 检查是否需要重试
            if self.stats["reconnect_attempts"] < self.max_reconnect_attempts:
                self.logger.info(f"WebSocketClient: 将在 {self.reconnect_interval} 秒后重试连接")
                self.log_message.emit(f"将在 {self.reconnect_interval} 秒后重试连接")
                await asyncio.sleep(self.reconnect_interval)
                asyncio.create_task(self._attempt_connect()) # 重试连接
            else:
                error_msg = f"WebSocketClient: 已达到最大重连尝试次数 ({self.max_reconnect_attempts})"
                self.logger.error(error_msg)
                self.error_occurred.emit("最大重连次数", error_msg)
                self.log_message.emit(error_msg)
                
                # 确保UI状态更新为已停止
                self.connection_status_changed.emit(False, "已达到最大重试次数")

    async def _connect(self):
        """建立WebSocket连接并设置接收消息任务"""
        try:
            # 建立到WebSocket服务器的连接
            self.websocket = await websockets.connect(
                self.websocket_uri,
                ping_interval=30,  # 设置心跳间隔
                ping_timeout=10    # 设置心跳超时
            )
            
            # 更新连接状态
            self.connected = True
            log_msg = f"WebSocketClient: 已成功连接到 {self.websocket_uri}"
            self.logger.info(log_msg)
            self.log_message.emit(log_msg)
            self.connection_status_changed.emit(True, "已连接")
            
            # 创建并启动接收消息的异步任务
            self._receive_task = asyncio.create_task(self._receive_messages_task())
            
            # 重置重连计数
            self.stats["reconnect_attempts"] = 0
            
            return True
            
        except Exception as e:
            # 更新连接状态和错误统计
            self.connected = False
            self.stats["connection_errors"] += 1
            
            error_msg = f"WebSocketClient: 连接到 {self.websocket_uri} 时出错: {str(e)}"
            self.logger.error(error_msg)
            self.log_message.emit(error_msg)
            self.error_occurred.emit("连接错误", str(e))
            
            # 抛出异常以便调用者处理
            raise

    async def _receive_messages_task(self):
        """Async task to continuously receive messages from the WebSocket"""
        log_msg = "WebSocketClient: Receive messages task started."
        self.logger.info(log_msg)
        self.log_message.emit(log_msg)

        while self.connected and self.running and not self._stop_requested:
            try:
                raw_message = await self.websocket.recv()
                self.stats["messages_received"] += 1

                # Removed: log_msg = f"WebSocketClient: 收到原始消息: {raw_message[:200]}..."
                # Removed: self.logger.debug(log_msg)
                # Removed: self.log_message.emit(log_msg)

                # Emit signal to process the raw message in a sync slot
                self._message_received_internal.emit(raw_message)

            except websockets.exceptions.ConnectionClosedOK:
                log_msg = "WebSocketClient: Connection closed gracefully."
                self.logger.info(log_msg)
                self.log_message.emit(log_msg)
                break # Exit loop on graceful close
            except websockets.exceptions.ConnectionClosed as e:
                self.connected = False
                error_msg = f"WebSocketClient: Connection closed unexpectedly: {e}"
                self.logger.warning(error_msg)
                self.log_message.emit(error_msg)
                self.connection_status_changed.emit(False, f"连接已关闭: {e}")
                # Attempt reconnect if running and not stopped
                if self.running and not self._stop_requested:
                     self._connection_timer.start(self.reconnect_interval * 1000)
                break # Exit loop on unexpected close
            except asyncio.CancelledError:
                log_msg = "WebSocketClient: Receive task cancelled."
                self.logger.info(log_msg)
                self.log_message.emit(log_msg)
                break # Exit loop when task is cancelled
            except Exception as e:
                self.stats["processing_errors"] += 1 # Or a new stat for receive errors?
                error_msg = f"WebSocketClient: Error receiving message: {e}"
                self.logger.error(error_msg, exc_info=True)
                self.log_message.emit(f"ERROR: {error_msg}")
                self.error_occurred.emit("接收错误", error_msg)
                # Continue loop? Or break? Let's break for now on unexpected errors
                break # Exit loop on other errors

        log_msg = "WebSocketClient: Receive messages task finished."
        self.logger.info(log_msg)
        self.log_message.emit(log_msg)
        self.connected = False # Ensure connected is False when task finishes
        self.connection_status_changed.emit(False, "接收任务结束")


    @pyqtSlot(str)
    def _process_raw_message(self, raw_message: str):
        """Process a raw message string (runs in worker thread)"""
        try:
            # Use the MessageParser to process the raw message
            # Note: MessageParser.process_message is NOT async, so it can be called directly
            processed_message = self.processor.process_message(raw_message)

            if processed_message:
                self.stats["messages_processed"] += 1

                # Clean the processed message
                cleaned_content = self.cleaner.clean_message(processed_message)

                if cleaned_content is not None:
                    # Only log successful processing if the cleaner returned content (i.e., it was a comment)
                    log_msg = f"WebSocketClient: Comment successfully cleaned."
                    self.logger.debug(log_msg)
                    self.log_message.emit(log_msg) # Emit log signal

                    # 如果消息清理成功（返回内容）并且有回调，调用所有回调函数
                    if self.message_callbacks:
                        for callback in self.message_callbacks:
                            try:
                                # 调用回调函数处理清理后的内容（字符串）
                                callback(cleaned_content)
                            except Exception as e:
                                error_msg = f"WebSocketClient: Error in message callback function: {e}"
                                self.logger.error(error_msg)
                                self.log_message.emit(f"ERROR: {error_msg}") # Emit log signal for error
                                self.error_occurred.emit("回调错误", f"处理消息回调函数时出错: {e}") # Emit error signal
                else:
                    self.stats["messages_filtered"] += 1
                    # Removed: log_msg = "WebSocketClient: Message filtered by cleaner."
                    # Removed: self.logger.debug(log_msg)
                    # Removed: self.log_message.emit(log_msg) # Emit log signal

            else:
                self.stats["messages_filtered"] += 1
                # Removed: log_msg = "WebSocketClient: Message filtered by parser."
                # Removed: self.logger.debug(log_msg)
                # Removed: self.log_message.emit(log_msg) # Emit log signal

        except Exception as e:
            self.stats["processing_errors"] += 1
            error_message = f"处理原始消息时出错: {e}"
            self.logger.error(f"WebSocketClient: {error_message}", exc_info=True)
            self.log_message.emit(f"ERROR: {error_message}") # Emit log signal for error
            self.error_occurred.emit("处理错误", error_message) # Emit error signal

    def set_message_callback(self, callback: Callable[[str], None]): # Updated type hint
        """Set the message processing callback function (expects string content)"""
        # 如果回调不在列表中，添加到回调列表
        if callback not in self.message_callbacks:
            self.message_callbacks.append(callback)
            self.logger.info("WebSocketClient: Added new message callback function.")

    def get_status(self) -> Dict[str, Any]:
        """Get client current status and stats"""
        status = {
            "connected": self.connected,
            "running": self.running,
            "websocket_uri": self.websocket_uri,
            "stats": self.stats
        }

        # Calculate filter rate
        total_messages = self.stats["messages_processed"] + self.stats["messages_filtered"]
        if total_messages > 0:
            filter_rate = (self.stats["messages_filtered"] / total_messages) * 100
            status["filter_rate"] = f"{filter_rate:.1f}%"
        else:
            status["filter_rate"] = "N/A"

        return status

    def is_connected(self) -> bool:
        """Check if the WebSocket client is currently connected"""
        return self.connected

# Example usage (for testing the client in isolation if needed)
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Create callback function
    def message_handler(processed_message):
        msg_type = processed_message.get('type', 'unknown')
        print(f"Received {msg_type} type message")

    # Example of how it would be used with qasync in a QThread:
    from PyQt6.QtCore import QThread, QCoreApplication
    import asyncio
    from qasync import QEventLoop

    app = QCoreApplication([])
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    thread = QThread()
    # Pass the event loop to the worker if needed, or ensure worker uses the current loop
    client = WebSocketClient(websocket_uri="ws://127.0.0.1:8888", message_callback=message_handler)
    client.moveToThread(thread)

    # Connect signals/slots
    thread.started.connect(client.start)
    client.connection_status_changed.connect(lambda is_connected, msg: print(f"Connection Status: {is_connected} - {msg}"))
    client.error_occurred.connect(lambda type, msg: print(f"Error: {type} - {msg}"))
    client.log_message.connect(lambda msg: print(f"Client Log: {msg}"))

    # Connect thread finished
    thread.finished.connect(thread.deleteLater)
    client.destroyed.connect(thread.quit)

    # Start the thread
    thread.start()

    # Run the application event loop
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        print("Stopping client...")
        client.stop() # Call the async stop method
        loop.run_until_complete(asyncio.gather(*asyncio.all_tasks(loop=loop))) # Wait for async tasks to finish
        thread.quit()
        thread.wait()
    print("Client stopped")
