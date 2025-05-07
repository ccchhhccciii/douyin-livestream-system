"""
websocket_service_test_ui.py - 抖音直播WebSocket服务测试UI

这是一个简单的测试界面，专注于显示从websocket_service.py中接收到的消息。
DouYinCommentService已经处理了连接、重连和消息处理等功能。
"""

import sys
import os
import time
import logging
import asyncio
from typing import Dict, Any, Optional

# 添加项目根目录到系统路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../.."))
sys.path.append(project_root)

# PyQt6相关导入
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                          QHBoxLayout, QPushButton, QLabel, QTextEdit,
                          QMessageBox)
from PyQt6.QtCore import pyqtSlot, QTimer, Qt

# 导入qasync库以支持异步操作
import qasync
from qasync import QEventLoop, asyncSlot

# 导入WebSocket服务
from modules.websocket.websocket_service import DouYinCommentService

# 设置日志记录
def setup_logging():
    """设置日志记录"""
    # 创建日志目录
    log_dir = os.path.join(project_root, "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    # 设置文件日志
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    log_file = os.path.join(log_dir, f"websocket_test_{timestamp}.log")
    
    # 配置日志格式和级别
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # 设置文件处理器
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(logging.Formatter(log_format))
    
    # 设置控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(log_format))
    
    # 配置根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # 检查根日志记录器是否已有处理器，避免重复添加
    has_file_handler = any(isinstance(h, logging.FileHandler) for h in root_logger.handlers)
    has_console_handler = any(isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler) for h in root_logger.handlers)
    
    if not has_file_handler:
        root_logger.addHandler(file_handler)
    
    if not has_console_handler:
        root_logger.addHandler(console_handler)
    
    # 获取应用日志记录器
    logger = logging.getLogger(__name__)
    logger.info(f"日志文件: {log_file}")
    
    return logger

class WebSocketServiceTestUI(QMainWindow):
    """WebSocket服务测试UI界面，专注于显示接收到的消息"""
    
    def __init__(self):
        """初始化测试UI界面"""
        super().__init__()
        
        # 设置日志
        self.logger = setup_logging()
        self.logger.info("启动WebSocket服务测试UI")
        
        # 设置窗口
        self.setWindowTitle("抖音WebSocket服务测试")
        self.resize(600, 500)
        
        # 初始化UI组件
        self._setup_ui()
        
        # 初始化WebSocket服务
        self._init_websocket_service()
        
        # 设置状态更新定时器
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(1000)  # 每秒更新一次
        
        self.statusBar().showMessage("系统就绪")
    
    def _setup_ui(self):
        """设置UI界面"""
        # 创建中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # 顶部控制面板
        control_layout = QHBoxLayout()
        
        # 连接控制和状态显示
        self.connect_button = QPushButton("连接WebSocket")
        self.connect_button.clicked.connect(self.toggle_connection)
        control_layout.addWidget(self.connect_button)
        
        self.ws_status_label = QLabel("未连接")
        control_layout.addWidget(self.ws_status_label)
        
        # 添加服务器地址输入
        control_layout.addWidget(QLabel("服务器地址:"))
        self.server_address = QTextEdit("ws://127.0.0.1:8888")
        self.server_address.setMaximumHeight(30)
        control_layout.addWidget(self.server_address)
        
        main_layout.addLayout(control_layout)
        
        # 收到的消息
        main_layout.addWidget(QLabel("收到的WebSocket消息:"))
        self.messages_list = QTextEdit()
        self.messages_list.setReadOnly(True)
        main_layout.addWidget(self.messages_list)
        
        # 清空按钮
        self.clear_button = QPushButton("清空消息")
        self.clear_button.clicked.connect(self.clear_messages)
        main_layout.addWidget(self.clear_button)
        
        # 日志区域
        main_layout.addWidget(QLabel("系统日志:"))
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        main_layout.addWidget(self.log_text)
    
    def _init_websocket_service(self):
        """初始化WebSocket服务"""
        try:
            # 创建WebSocket服务配置
            websocket_config = {
                "websocket_uri": "ws://127.0.0.1:8888",  # 默认抖音直播WebSocket服务器地址
                "processor_config": {
                    "filter_comments": False,  # 禁用过滤，确保所有评论都能通过
                    "clean_nickname": False,  # 禁用昵称清理
                    "allowed_message_types": [1]  # 只允许评论类型的消息（类型1）
                },
                "batch_size": 1  # 每收到1条评论就处理一次，方便测试
            }
            
            # 创建服务实例
            self.websocket_service = DouYinCommentService(websocket_config)
            
            # 设置外部回调函数来接收处理后的消息
            self.websocket_service.set_external_callback(self.on_websocket_message)
            
            self.log_message("WebSocket服务初始化完成")
            
        except Exception as e:
            self.logger.error(f"初始化WebSocket服务时出错: {e}", exc_info=True)
            self.show_error("初始化错误", f"初始化WebSocket服务时出错: {e}")
    
    @pyqtSlot(str)
    def log_message(self, message):
        """记录日志消息
        
        Args:
            message: 日志消息
        """
        if hasattr(self, 'log_text'):
            self.log_text.append(message)
            # 滚动到底部
            self.log_text.verticalScrollBar().setValue(
                self.log_text.verticalScrollBar().maximum()
            )
        self.logger.info(message)
    
    @pyqtSlot(str, str)
    def show_error(self, error_type, error_message):
        """显示错误消息
        
        Args:
            error_type: 错误类型
            error_message: 错误消息
        """
        self.logger.error(f"{error_type}: {error_message}")
        QMessageBox.critical(self, error_type, error_message)
    
    def toggle_connection(self):
        """切换WebSocket连接状态"""
        try:
            if not hasattr(self, 'websocket_service'):
                self.show_error("连接错误", "WebSocket服务未初始化")
                return

            # 检查WebSocket连接状态
            is_connected = self.websocket_service.running

            if not is_connected:
                # 更新服务器地址
                websocket_uri = self.server_address.toPlainText().strip()
                if not websocket_uri:
                    self.show_error("连接错误", "请输入有效的WebSocket服务器地址")
                    return
                
                # 更新配置
                self.websocket_service.config["websocket_uri"] = websocket_uri
                self.websocket_service.websocket_client.websocket_uri = websocket_uri
                
                self.connect_button.setEnabled(False)  # 禁用按钮防止重复点击
                self.connect_button.setText("正在连接...")
                self.ws_status_label.setText("正在连接...")
                self.log_message(f"正在连接WebSocket服务器: {websocket_uri}")
                
                # 启动WebSocket服务
                self.websocket_service.start()
                
            else:
                self.connect_button.setEnabled(False)  # 禁用按钮防止重复点击
                self.connect_button.setText("正在断开...")
                self.ws_status_label.setText("正在断开...")
                self.log_message("正在断开WebSocket连接...")
                
                # 异步停止WebSocket服务
                asyncio.ensure_future(self.websocket_service.stop())
                
        except Exception as e:
            self.logger.error(f"切换WebSocket连接时出错: {e}", exc_info=True)
            self.show_error("连接错误", f"WebSocket连接操作失败: {e}")
            self.connect_button.setEnabled(True)
            self.connect_button.setText("连接WebSocket")
    
    def on_websocket_message(self, cleaned_content):
        """处理WebSocket接收到的消息
        
        Args:
            cleaned_content: 从WebSocket服务接收到的内容
        """
        # 记录日志
        self.log_message(f"收到WebSocket消息: {cleaned_content}")
        
        # 显示在UI上 - 不添加时间戳
        if hasattr(self, 'messages_list'):
            self.messages_list.append(cleaned_content)
            # 滚动到底部
            self.messages_list.verticalScrollBar().setValue(
                self.messages_list.verticalScrollBar().maximum()
            )
    
    def clear_messages(self):
        """清空消息列表"""
        if hasattr(self, 'messages_list'):
            self.messages_list.clear()
            self.log_message("已清空消息列表")
    
    def update_status(self):
        """更新状态显示"""
        if not hasattr(self, 'websocket_service'):
            return
            
        # 更新WebSocket连接状态
        is_connected = self.websocket_service.running
        
        # 根据状态更新颜色
        if is_connected:
            self.ws_status_label.setText("已连接")
            self.ws_status_label.setStyleSheet("color: green; font-weight: bold;")
            self.connect_button.setText("断开WebSocket")
            self.connect_button.setEnabled(True)
        else:
            self.ws_status_label.setText("未连接")
            self.ws_status_label.setStyleSheet("color: red;")
            self.connect_button.setText("连接WebSocket")
            self.connect_button.setEnabled(True)
    
    @asyncSlot()
    async def closeEvent(self, event):
        """处理窗口关闭事件
        
        Args:
            event: 关闭事件
        """
        self.logger.info("应用正在关闭...")
        
        # 停止定时器
        if hasattr(self, 'status_timer'):
            self.status_timer.stop()
        
        # 停止WebSocket服务
        if hasattr(self, 'websocket_service') and self.websocket_service.running:
            await self.websocket_service.stop()
            self.logger.info("WebSocket服务已停止")
        
        self.logger.info("应用清理完成")
        event.accept()

# 应用入口点
if __name__ == "__main__":
    # 创建应用
    app = QApplication(sys.argv)
    
    # 设置qasync事件循环
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    
    # 创建主窗口
    window = WebSocketServiceTestUI()
    window.show()
    
    # 在qasync事件循环中运行
    with loop:
        loop.run_forever()
