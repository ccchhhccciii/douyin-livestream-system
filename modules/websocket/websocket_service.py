"""
websocket_service.py - 抖音直播评论处理微服务

该服务连接到抖音直播WebSocket服务器，接收和处理直播评论，
并将清理后的评论传递给LLM进行回复生成。
"""

import asyncio
import logging
import json
import os
import sys
import signal
from datetime import datetime
from typing import Dict, Any, Optional, List, Union, Callable

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 导入自定义模块
from modules.websocket.message_parser import MessageParser
from modules.websocket.message_clean import MessageCleaner
from modules.websocket.websocket_client import WebSocketClient
import websockets  # 显式导入websockets模块

# 配置日志
# 确保日志目录存在于项目根目录中
logs_dir = os.path.join(project_root, "logs")
os.makedirs(logs_dir, exist_ok=True)

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

logger = logging.getLogger("DouYinCommentService")

# 创建扩展的WebSocketClient子类，添加缺失的_connect方法
class ExtendedWebSocketClient(WebSocketClient):
    """扩展的WebSocket客户端，添加缺失的_connect方法"""
    
    async def _connect(self):
        """建立WebSocket连接的方法"""
        try:
            self.logger.info(f"ExtendedWebSocketClient: 正在连接到 {self.websocket_uri}")
            
            # 创建WebSocket连接
            self.websocket = await websockets.connect(
                self.websocket_uri,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=5
            )
            
            # 更新连接状态
            self.connected = True
            self.connection_status_changed.emit(True, "已连接")
            self.log_message.emit(f"已成功连接到 {self.websocket_uri}")
            
            # 启动接收消息任务
            self._receive_task = asyncio.create_task(self._receive_messages_task())
            
            return self.websocket
            
        except asyncio.CancelledError:
            self.logger.info("ExtendedWebSocketClient: 连接任务被取消")
            self.connected = False
            raise  # 重新抛出取消异常
            
        except Exception as e:
            self.logger.error(f"ExtendedWebSocketClient: 连接到 {self.websocket_uri} 失败: {type(e).__name__}: {str(e)}")
            self.connected = False
            self.connection_status_changed.emit(False, f"连接失败: {str(e)}")
            raise  # 重新抛出异常，让调用者处理

class DouYinCommentService:
    """抖音直播评论处理微服务"""
    
    def __init__(self, config: Dict[str, Any], external_callback: Optional[Callable[[str], None]] = None):
        """
        初始化服务
        
        Args:
            config: 服务配置字典
            external_callback: 外部回调函数，用于将清理后的评论传递给外部系统
        """
        self.config = config
        self.logger = logger
        self.logger.info("正在初始化抖音评论处理服务...")
        
        # 外部回调函数，用于与UI层通信
        self.external_callback = external_callback
        
        # 创建消息清理器
        self.cleaner = MessageCleaner()
        
        # 保存已处理的评论，准备发送到LLM
        self.processed_comments: List[str] = []
        
        # 使用外部提供的WebSocketClient实例，或者创建一个新的ExtendedWebSocketClient实例
        if "client_instance" in config and isinstance(config["client_instance"], WebSocketClient):
            self.logger.info("使用外部提供的WebSocketClient实例")
            self.websocket_client = config["client_instance"]
        else:
            self.logger.info("创建新的ExtendedWebSocketClient实例")
            self.websocket_client = ExtendedWebSocketClient(
                websocket_uri=config.get("websocket_uri", "ws://127.0.0.1:8888"),
                processor_config=config.get("processor_config", {})
            )
        
        # 设置WebSocket客户端回调
        self.websocket_client.set_message_callback(self.handle_cleaned_comment)
        
        # 设置运行标志
        self.running = False
        
        # LLM请求队列
        self.llm_request_queue: List[str] = []
        self.queue_processing = False
        
        self.logger.info("抖音评论处理服务初始化完成")
    
    def set_external_callback(self, callback: Callable[[str], None]):
        """
        设置外部回调函数，用于将处理后的评论传递给UI或其他系统
        
        Args:
            callback: 回调函数，接收一个字符串参数(清理后的评论)
        """
        self.external_callback = callback
        self.logger.info("已设置外部回调函数")
        
    def handle_cleaned_comment(self, cleaned_content: str):
        """
        处理清理后的评论
        
        Args:
            cleaned_content: 清理后的评论内容
        """
        self.logger.info(f"收到清理后的评论: {cleaned_content}")
        
        # 将清理后的评论添加到处理队列
        self.processed_comments.append(cleaned_content)
        
        # 如果设置了外部回调，则调用它传递清理后的评论
        if self.external_callback:
            try:
                self.logger.debug("调用外部回调函数传递评论")
                self.external_callback(cleaned_content)
            except Exception as e:
                self.logger.error(f"调用外部回调函数时出错: {e}", exc_info=True)
        else:
            self.logger.warning("未设置外部回调函数，无法将评论传递给外部系统")
        
        # 检查是否需要批量处理评论
        if len(self.processed_comments) >= self.config.get("batch_size", 5):
            self.process_comments_batch()
            
    def process_comments_batch(self):
        """处理一批评论（发送到LLM）"""
        if not self.processed_comments:
            return
            
        comments_to_process = self.processed_comments.copy()
        self.processed_comments.clear()
        
        self.logger.info(f"处理评论批次，共 {len(comments_to_process)} 条")
        
        # 将评论添加到LLM请求队列
        self.llm_request_queue.extend(comments_to_process)
        
        # 如果队列处理未运行，则启动它
        if not self.queue_processing and self.running:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self._process_llm_queue())
            else:
                # 如果没有运行中的事件循环，则记录警告
                self.logger.warning("无法处理LLM队列：没有运行中的事件循环")
    
    async def _process_llm_queue(self):
        """处理LLM请求队列的异步任务"""
        self.queue_processing = True
        
        try:
            while self.llm_request_queue and self.running:
                # 从队列中取出一条评论
                comment = self.llm_request_queue.pop(0)
                
                # 模拟与LLM通信延迟
                self.logger.info(f"正在处理LLM请求: {comment}")
                await asyncio.sleep(0.5)  # 模拟API调用延迟
                
                # 实际应用中，这里会调用LLM服务API
                # response = await self._call_llm_api(comment)
                response = f"这是LLM对评论'{comment}'的模拟回复"
                
                self.logger.info(f"从LLM获取的回复: {response}")
                
                # TODO: 将LLM回复传递给响应处理系统
                # 这里可以添加一个回调函数来处理LLM回复
        except Exception as e:
            self.logger.error(f"处理LLM队列时出错: {e}", exc_info=True)
        finally:
            self.queue_processing = False

    def start(self):
        """启动服务（非异步版本，适用于在PyQt应用中调用）"""
        if self.running:
            self.logger.warning("服务已经在运行")
            return False
            
        self.logger.info("启动抖音评论处理服务...")
        self.running = True
        
        # 启动WebSocket客户端
        success = self.websocket_client.start()
        if not success:
            self.logger.error("启动WebSocket客户端失败")
            self.running = False
            return False
            
        self.logger.info("抖音评论处理服务已启动")
        return True
            
    async def start_async(self):
        """启动服务 (异步版本)"""
        if self.running:
            self.logger.warning("服务已经在运行")
            return False
            
        self.logger.info("启动抖音评论处理服务...")
        self.running = True
        
        # 启动WebSocket客户端
        success = self.websocket_client.start()
        if not success:
            self.logger.error("启动WebSocket客户端失败")
            self.running = False
            return False
            
        self.logger.info("抖音评论处理服务已启动")
        return True
        
    async def stop(self):
        """停止服务"""
        if not self.running:
            self.logger.warning("服务未在运行")
            return
            
        self.logger.info("正在停止抖音评论处理服务...")
        self.running = False
        
        # 停止WebSocket客户端
        await self.websocket_client.stop()
        
        # 处理剩余的评论
        if self.processed_comments:
            # 只记录，不实际处理，因为服务正在关闭
            self.logger.info(f"服务关闭，有 {len(self.processed_comments)} 条未处理的评论")
            self.processed_comments.clear()
        
        # 清空LLM请求队列
        queue_size = len(self.llm_request_queue)
        if queue_size > 0:
            self.logger.info(f"服务关闭，清空LLM请求队列，丢弃 {queue_size} 条请求")
            self.llm_request_queue.clear()
            
        self.logger.info("抖音评论处理服务已停止")
        
    async def _call_llm_api(self, message: str) -> str:
        """
        调用LLM API获取回复
        
        Args:
            message: 要发送给LLM的消息
            
        Returns:
            LLM生成的回复
        """
        # TODO: 实现与特定LLM API的集成
        # 这里只是一个示例实现
        try:
            # 模拟API调用延迟
            await asyncio.sleep(1)
            
            # 返回模拟回复
            return f"这是LLM回复: 感谢您的留言 - {message}"
        except Exception as e:
            self.logger.error(f"调用LLM API时出错: {e}", exc_info=True)
            return "抱歉，无法生成回复"

# 独立服务入口点
async def main():
    """主函数，用于独立运行服务"""
    # 创建配置
    config = {
        "websocket_uri": "ws://127.0.0.1:8888",  # 抖音直播WebSocket服务器地址
        "processor_config": {
            "filter_comments": True,
            "clean_nickname": True,
            "allowed_message_types": [1]  # 只处理评论消息
        },
        "batch_size": 3  # 每收集3条评论处理一次
    }
    
    # 创建服务实例
    service = DouYinCommentService(config)
    
    # 注册信号处理器（仅在支持的平台上）
    loop = asyncio.get_event_loop()
    
    try:
        import os
        if os.name != 'nt':  # 不是 Windows
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown(service)))
        else:
            print("注意：在 Windows 平台上不支持asyncio信号处理器，请使用 Ctrl+C 停止")
    except (NotImplementedError, ImportError):
        print("注意：此平台不支持异步信号处理器，请使用 Ctrl+C 停止")
    
    # 启动服务
    await service.start_async()
    
    # 保持运行直到收到停止信号
    try:
        while service.running:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    finally:
        if service.running:
            await service.stop()

async def shutdown(service: DouYinCommentService):
    """优雅关闭服务"""
    logger.info("收到关闭信号，准备关闭服务...")
    await service.stop()
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    asyncio.get_event_loop().stop()

if __name__ == "__main__":
    # 确保日志目录存在
    os.makedirs(logs_dir, exist_ok=True)
    
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            UnicodeStreamHandler(),
            logging.FileHandler(
                os.path.join(logs_dir, f"douyin_service_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
                encoding='utf-8'
            )
        ]
    )
    
    # 运行主函数
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n服务已通过键盘中断关闭")
    except Exception as e:
        logger.exception(f"服务运行错误: {e}")
        sys.exit(1)
