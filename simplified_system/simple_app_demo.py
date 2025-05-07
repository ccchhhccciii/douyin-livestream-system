"""
抖音电商无人直播系统 - 极简演示应用
基于simple_livestream_system.py创建的非阻塞UI应用
解决了UI线程阻塞问题
"""

import os
import sys
import logging
from datetime import datetime
import time

# 添加项目根目录到系统路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 导入简化版系统核心
from simplified_system.simple_livestream_system import SimpleStreamSystem

# PyQt6相关导入
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                          QHBoxLayout, QPushButton, QLabel, QTextEdit,
                          QListWidget, QMessageBox, QInputDialog)
from PyQt6.QtCore import Qt, pyqtSlot, QTimer


class SimpleAppDemo(QMainWindow):
    """极简版用户界面演示"""
    
    def __init__(self):
        """初始化用户界面"""
        super().__init__()
        
        # 设置日志
        self._setup_logging()
        self.logger.info("启动极简版直播系统演示UI")
        
        # 设置窗口
        self.setWindowTitle("抖音直播系统 - 极简演示版")
        self.resize(800, 600)
        
        # 创建直播系统实例
        self.stream_system = SimpleStreamSystem()
        
        # 连接信号
        self._connect_signals()
        
        # 初始化UI组件
        self._setup_ui()
        
        self.logger.info("极简版直播系统演示UI初始化完成")
        self.statusBar().showMessage("系统就绪")
    
    def _setup_logging(self):
        """设置日志记录"""
        # 创建日志目录
        log_dir = os.path.join(project_root, "data", "logs")
        os.makedirs(log_dir, exist_ok=True)
        
        # 设置文件日志
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        log_file = os.path.join(log_dir, f"simple_app_demo_{timestamp}.log")
        
        # 配置日志格式和级别
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        
        # 配置根日志记录器
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        
        # 清除已有的处理器以避免重复输出
        root_logger.handlers = []
        
        # 添加文件处理器
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter(log_format))
        root_logger.addHandler(file_handler)
        
        # 添加控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(log_format))
        root_logger.addHandler(console_handler)
        
        # 获取应用日志记录器
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info(f"日志文件: {log_file}")
    
    def _connect_signals(self):
        """连接系统信号"""
        # 连接系统状态信号
        self.stream_system.system_status_changed.connect(self._on_system_status_changed)
        
        # 连接消息信号
        self.stream_system.message_received.connect(self._on_message_received)
        self.stream_system.response_generated.connect(self._on_response_generated)
        
        # 连接日志和错误信号
        self.stream_system.log_message.connect(self._on_log_message)
        self.stream_system.error_occurred.connect(self._on_error_occurred)
    
    def _setup_ui(self):
        """设置UI组件"""
        # 创建中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # 顶部控制面板
        control_layout = QHBoxLayout()
        
        # 状态标签
        self.status_label = QLabel("WebSocket状态: 未连接")
        self.status_label.setStyleSheet("color: red;")
        control_layout.addWidget(self.status_label)
        
        # 控制按钮
        self.start_button = QPushButton("启动系统")
        self.start_button.clicked.connect(self._on_start_clicked)
        control_layout.addWidget(self.start_button)
        
        self.stop_button = QPushButton("停止系统")
        self.stop_button.clicked.connect(self._on_stop_clicked)
        self.stop_button.setEnabled(False)
        control_layout.addWidget(self.stop_button)
        
        control_layout.addStretch(1)
        main_layout.addLayout(control_layout)
        
        # 创建中央内容区域 - 分为左右两部分
        content_layout = QHBoxLayout()
        
        # 左侧区域 - 用户消息和系统回复
        left_layout = QVBoxLayout()
        
        # 用户消息
        left_layout.addWidget(QLabel("用户消息:"))
        self.messages_list = QListWidget()
        left_layout.addWidget(self.messages_list)
        
        # 测试消息按钮
        test_message_layout = QHBoxLayout()
        self.test_message_button = QPushButton("发送测试消息")
        self.test_message_button.clicked.connect(self._on_test_message_clicked)
        test_message_layout.addWidget(self.test_message_button)
        
        self.custom_message_button = QPushButton("发送自定义消息")
        self.custom_message_button.clicked.connect(self._on_custom_message_clicked)
        test_message_layout.addWidget(self.custom_message_button)
        
        left_layout.addLayout(test_message_layout)
        
        # 系统回复
        left_layout.addWidget(QLabel("系统回复:"))
        self.responses_list = QListWidget()
        left_layout.addWidget(self.responses_list)
        
        # 添加自定义话术按钮
        self.add_script_button = QPushButton("添加自定义话术")
        self.add_script_button.clicked.connect(self._on_add_script_clicked)
        left_layout.addWidget(self.add_script_button)
        
        content_layout.addLayout(left_layout)
        
        # 右侧区域 - 系统日志
        right_layout = QVBoxLayout()
        
        right_layout.addWidget(QLabel("系统日志:"))
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        right_layout.addWidget(self.log_text)
        
        # 清空日志按钮
        self.clear_log_button = QPushButton("清空日志")
        self.clear_log_button.clicked.connect(lambda: self.log_text.clear())
        right_layout.addWidget(self.clear_log_button)
        
        content_layout.addLayout(right_layout)
        
        # 设置左右区域的宽度比例
        content_layout.setStretch(0, 3)  # 左侧区域
        content_layout.setStretch(1, 2)  # 右侧区域
        
        main_layout.addLayout(content_layout)
        
        # 创建UI更新定时器，确保UI响应性
        self.ui_timer = QTimer(self)
        self.ui_timer.timeout.connect(self._update_ui)
        self.ui_timer.start(500)  # 每500毫秒更新一次UI
    
    def _update_ui(self):
        """更新UI状态，确保响应性"""
        # 处理任何挂起的Qt事件
        QApplication.processEvents()
    
    def _on_start_clicked(self):
        """启动按钮点击事件"""
        self.logger.info("用户点击启动按钮")
        
        # 禁用启动按钮
        self.start_button.setEnabled(False)
        self.start_button.setText("正在启动...")
        
        # 使用单独的定时器启动系统，避免阻塞UI
        QTimer.singleShot(0, self._start_system)
    
    def _start_system(self):
        """启动系统（通过定时器调用，避免阻塞UI）"""
        try:
            # 启动系统
            success = self.stream_system.start()
            
            if success:
                # 启用停止按钮
                self.stop_button.setEnabled(True)
                self.log_message("系统已启动")
                self.statusBar().showMessage("系统运行中")
            else:
                # 重新启用启动按钮
                self.start_button.setEnabled(True)
                self.start_button.setText("启动系统")
                self.log_message("系统启动失败")
                self.statusBar().showMessage("系统启动失败")
                
        except Exception as e:
            self.logger.error(f"启动系统时出错: {e}", exc_info=True)
            self.log_message(f"启动系统时出错: {e}")
            
            # 重新启用启动按钮
            self.start_button.setEnabled(True)
            self.start_button.setText("启动系统")
    
    def _on_stop_clicked(self):
        """停止按钮点击事件"""
        self.logger.info("用户点击停止按钮")
        
        # 禁用停止按钮
        self.stop_button.setEnabled(False)
        self.stop_button.setText("正在停止...")
        
        # 使用单独的定时器停止系统，避免阻塞UI
        QTimer.singleShot(0, self._stop_system)
    
    def _stop_system(self):
        """停止系统（通过定时器调用，避免阻塞UI）"""
        try:
            # 停止系统
            self.stream_system.stop()
            
            # 更新UI状态
            self.start_button.setEnabled(True)
            self.start_button.setText("启动系统")
            self.stop_button.setText("停止系统")
            self.log_message("系统已停止")
            self.statusBar().showMessage("系统已停止")
            
        except Exception as e:
            self.logger.error(f"停止系统时出错: {e}", exc_info=True)
            self.log_message(f"停止系统时出错: {e}")
            
            # 重置按钮状态
            self.stop_button.setEnabled(True)
            self.stop_button.setText("停止系统")
    
    def _on_test_message_clicked(self):
        """测试消息按钮点击事件"""
        self.logger.info("用户点击测试消息按钮")
        
        # 检查系统是否在运行
        if not self.stream_system.is_running():
            QMessageBox.warning(self, "系统未运行", "请先启动系统")
            return
        
        # 禁用按钮防止重复点击
        self.test_message_button.setEnabled(False)
        
        # 测试消息列表
        test_messages = [
            "你好，请问这个产品怎么样？",
            "这个产品的价格是多少？",
            "有什么优惠活动吗？",
            "发货时间大概是多久？",
            "支持七天无理由退货吗？",
            "这个产品的质量好吗？"
        ]
        
        # 选择一个测试消息
        import random
        message = random.choice(test_messages)
        
        # 使用定时器添加消息，避免阻塞UI
        QTimer.singleShot(0, lambda: self._send_message(message))
        
        # 延时重新启用按钮，防止频繁发送
        QTimer.singleShot(1000, lambda: self.test_message_button.setEnabled(True))
    
    def _on_custom_message_clicked(self):
        """自定义消息按钮点击事件"""
        self.logger.info("用户点击自定义消息按钮")
        
        # 检查系统是否在运行
        if not self.stream_system.is_running():
            QMessageBox.warning(self, "系统未运行", "请先启动系统")
            return
        
        # 弹出输入对话框
        text, ok = QInputDialog.getText(self, "输入自定义消息", "请输入消息内容:")
        
        if ok and text.strip():
            # 使用定时器添加消息，避免阻塞UI
            QTimer.singleShot(0, lambda: self._send_message(text))
    
    def _send_message(self, message: str):
        """发送消息到系统
        
        Args:
            message: 消息内容
        """
        self.logger.info(f"发送消息: {message}")
        success = self.stream_system.add_custom_message(message)
        
        if not success:
            self.log_message(f"发送消息失败: {message}")
    
    def _on_add_script_clicked(self):
        """添加自定义话术按钮点击事件"""
        self.logger.info("用户点击添加自定义话术按钮")
        
        # 检查系统是否在运行
        if not self.stream_system.is_running():
            QMessageBox.warning(self, "系统未运行", "请先启动系统")
            return
        
        # 弹出输入对话框
        text, ok = QInputDialog.getMultiLineText(self, "添加自定义话术", "请输入话术内容:")
        
        if ok and text.strip():
            # 使用定时器添加话术，避免阻塞UI
            QTimer.singleShot(0, lambda: self._add_script(text))
    
    def _add_script(self, script: str):
        """添加话术到系统
        
        Args:
            script: 话术内容
        """
        self.logger.info(f"添加话术: {script}")
        success = self.stream_system.add_custom_script(script)
        
        if not success:
            self.log_message(f"添加话术失败: {script}")
    
    @pyqtSlot(str, bool, str)
    def _on_system_status_changed(self, service_name: str, is_running: bool, message: str):
        """系统状态变化事件
        
        Args:
            service_name: 服务名称
            is_running: 是否运行
            message: 状态消息
        """
        self.logger.info(f"系统状态变化: {service_name} - {'运行中' if is_running else '已停止'} - {message}")
        
        # 更新状态显示
        if service_name == "websocket":
            if is_running:
                self.status_label.setText("WebSocket状态: 已连接")
                self.status_label.setStyleSheet("color: green; font-weight: bold;")
            else:
                self.status_label.setText("WebSocket状态: 未连接")
                self.status_label.setStyleSheet("color: red;")
    
    @pyqtSlot(str)
    def _on_message_received(self, message: str):
        """收到消息事件
        
        Args:
            message: 消息内容
        """
        self.logger.info(f"收到消息: {message}")
        
        # 添加到消息列表
        self.messages_list.addItem(f"用户: {message}")
        self.messages_list.scrollToBottom()
        
        # 清理过多的消息
        self._trim_list_widget(self.messages_list, 100)
    
    @pyqtSlot(str, dict)
    def _on_response_generated(self, response: str, context: dict):
        """响应生成事件
        
        Args:
            response: 响应内容
            context: 上下文信息
        """
        self.logger.info(f"生成响应: {response}")
        
        # 添加到响应列表
        self.responses_list.addItem(f"系统: {response}")
        self.responses_list.scrollToBottom()
        
        # 清理过多的响应
        self._trim_list_widget(self.responses_list, 100)
    
    @pyqtSlot(str)
    def _on_log_message(self, message: str):
        """日志消息事件
        
        Args:
            message: 日志消息
        """
        self.log_message(message)
    
    @pyqtSlot(str, str)
    def _on_error_occurred(self, error_type: str, error_message: str):
        """错误事件
        
        Args:
            error_type: 错误类型
            error_message: 错误消息
        """
        self.logger.error(f"{error_type}: {error_message}")
        
        # 在日志中显示错误
        self.log_message(f"错误: {error_type} - {error_message}")
        
        # 显示错误对话框
        QMessageBox.critical(self, error_type, error_message)
    
    def log_message(self, message: str):
        """记录日志消息
        
        Args:
            message: 日志消息
        """
        # 添加时间戳
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        
        # 添加到日志显示
        self.log_text.append(formatted_message)
        
        # 滚动到底部
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )
    
    def _trim_list_widget(self, list_widget, max_items=100):
        """限制列表项目数量
        
        Args:
            list_widget: 列表部件
            max_items: 最大项目数
        """
        count = list_widget.count()
        if count > max_items:
            # 移除多余的项目
            for i in range(count - max_items):
                list_widget.takeItem(0)
    
    def closeEvent(self, event):
        """窗口关闭事件
        
        Args:
            event: 关闭事件
        """
        self.logger.info("用户关闭窗口")
        
        # 如果系统正在运行，停止系统
        if self.stream_system.is_running():
            # 停止定时器
            if hasattr(self, 'ui_timer') and self.ui_timer.isActive():
                self.ui_timer.stop()
                
            # 停止系统
            self.logger.info("正在停止流式系统...")
            self.stream_system.stop()
            self.logger.info("流式系统停止完成")
        
        self.logger.info("关闭事件处理完成")
        event.accept()


# 应用入口点
if __name__ == "__main__":
    try:
        # 创建应用
        app = QApplication(sys.argv)
        
        # 创建主窗口
        window = SimpleAppDemo()
        window.show()
        
        # 运行应用
        sys.exit(app.exec())
    except Exception as e:
        print(f"程序启动异常: {e}")
        import traceback
        traceback.print_exc()
