"""
抖音电商无人直播系统 - 极简版运行脚本
用于启动简化版直播系统演示应用
"""

import os
import sys
import time
import logging
from pathlib import Path

# 添加项目根目录到系统路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def setup_logging():
    """设置日志记录"""
    # 创建日志目录
    log_dir = os.path.join(project_root, "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    # 配置日志格式和级别
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(os.path.join(log_dir, f"run_demo_{int(time.time())}.log"))
        ]
    )
    
    return logging.getLogger("RunSimpleDemo")

def check_environment():
    """检查环境配置"""
    logger = logging.getLogger("EnvironmentCheck")
    
    # 检查音频目录
    audio_dir = Path(project_root) / "data" / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"音频输出目录: {audio_dir}")
    
    # 检查PyQt
    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import QTimer
        logger.info("PyQt6环境检查通过")
    except ImportError:
        logger.error("未找到PyQt6，请安装: pip install PyQt6")
        return False
    
    # 检查websocket模拟服务器
    websocket_server = Path(project_root) / "websocket_simulation" / "websocket_server.py"
    if not websocket_server.exists():
        logger.warning(f"未找到WebSocket模拟服务器: {websocket_server}")
        logger.warning("系统将无法接收实时消息，但仍可以使用测试消息功能")
    else:
        logger.info(f"发现WebSocket模拟服务器: {websocket_server}")
    
    return True

def start_websocket_simulator():
    """尝试启动WebSocket模拟服务器"""
    logger = logging.getLogger("WebSocketSimulator")
    
    websocket_server = Path(project_root) / "websocket_simulation" / "websocket_server.py"
    if not websocket_server.exists():
        logger.warning("WebSocket模拟服务器不存在，跳过启动")
        return None
    
    try:
        import subprocess
        import threading
        
        def run_server():
            logger.info("正在启动WebSocket模拟服务器...")
            server_process = subprocess.Popen(
                [sys.executable, str(websocket_server)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # 读取和记录输出
            for line in server_process.stdout:
                logger.info(f"WebSocket服务器: {line.strip()}")
            
            for line in server_process.stderr:
                logger.error(f"WebSocket服务器错误: {line.strip()}")
            
            server_process.wait()
            logger.info(f"WebSocket模拟服务器已退出，返回代码: {server_process.returncode}")
        
        # 在线程中启动服务器
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        
        # 等待服务器启动
        time.sleep(1)
        logger.info("WebSocket模拟服务器启动成功")
        
        return server_thread
        
    except Exception as e:
        logger.error(f"启动WebSocket模拟服务器失败: {e}")
        return None

def main():
    """主函数"""
    # 设置日志
    logger = setup_logging()
    logger.info("启动抖音直播系统极简演示")
    
    # 检查环境
    if not check_environment():
        logger.error("环境检查失败，程序无法继续运行")
        return
    
    # 启动WebSocket模拟服务器
    server_thread = start_websocket_simulator()
    
    # 导入并启动演示应用
    try:
        from PyQt6.QtWidgets import QApplication
        from simplified_system.simple_app_demo import SimpleAppDemo
        
        logger.info("创建Qt应用")
        app = QApplication(sys.argv)
        
        logger.info("创建主窗口")
        window = SimpleAppDemo()
        window.show()
        
        logger.info("运行应用")
        sys.exit(app.exec())
        
    except Exception as e:
        logger.error(f"运行应用时出错: {e}", exc_info=True)

if __name__ == "__main__":
    main()
