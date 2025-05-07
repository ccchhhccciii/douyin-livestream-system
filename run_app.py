#!/usr/bin/env python3
"""
抖音电商自动直播工具启动脚本
"""

import sys
import os
import logging
import traceback

# 添加项目根目录到系统路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(project_root)

# 配置日志
def setup_logging():
    """设置日志记录"""
    # 创建日志目录
    log_dir = os.path.join(project_root, "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    # 设置日志文件
    log_file = os.path.join(log_dir, "app.log")
    
    # 配置日志格式
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # 设置日志级别
    logging.basicConfig(
        level=logging.DEBUG,
        format=log_format,
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    
    # 返回根日志记录器
    return logging.getLogger()

# 导入应用程序
def import_app():
    """导入应用程序模块"""
    try:
        from test.simple_app_ui import QApplication, SimpleAppUI
        return QApplication, SimpleAppUI
    except ImportError as e:
        logger.error(f"导入应用程序模块失败: {e}")
        print(f"错误: 导入应用程序模块失败: {e}")
        print(f"回溯:\n{traceback.format_exc()}")
        sys.exit(1)

def main():
    """启动应用程序"""
    logger.info("启动抖音电商自动直播工具")
    
    try:
        # 导入应用程序模块
        QApplication, SimpleAppUI = import_app()
        
        # 创建应用程序
        logger.debug("创建QApplication实例")
        app = QApplication(sys.argv)
        
        # 创建主窗口
        logger.debug("创建SimpleAppUI实例")
        window = SimpleAppUI()
        window.show()
        
        logger.info("应用程序已启动，进入主事件循环")
        
        # 运行应用程序
        return app.exec()
    
    except Exception as e:
        logger.critical(f"应用程序启动失败: {e}")
        print(f"严重错误: 应用程序启动失败: {e}")
        print(f"回溯:\n{traceback.format_exc()}")
        return 1

if __name__ == "__main__":
    # 设置日志
    logger = setup_logging()
    
    # 执行主函数
    try:
        exit_code = main()
        logger.info(f"应用程序退出，退出码: {exit_code}")
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("应用程序被用户中断")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"未捕获的异常: {e}")
        print(f"严重错误: {e}")
        print(f"回溯:\n{traceback.format_exc()}")
        sys.exit(1) 