"""
简化版TTS队列管理器
作为TTSQueueManager的备用实现，集成GPT-SOVITS客户端
"""

import os
import sys
import time
import threading
import queue
import logging
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Callable
from PyQt6.QtCore import QObject, pyqtSignal

# 添加项目根目录到sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 导入GPT-SOVITS客户端
from core.gptsovits_client import GPTSoVITSClient

# 导入Priority枚举
from modules.scheduler.text_queue import Priority

# 配置日志
logger = logging.getLogger(__name__)

class SimpleTTSQueueManager(QObject):
    """简化版TTS队列管理器

    负责管理TTS生成队列和音频播放队列，处理优先级调度。
    集成GPT-SOVITS客户端进行实际的TTS生成。
    """

    # 信号定义
    tts_started = pyqtSignal(str)  # 参数: item_id
    tts_completed = pyqtSignal(str, str)  # 参数: item_id, audio_path
    tts_failed = pyqtSignal(str, str)  # 参数: item_id, reason

    # 状态监控和统计信号
    queue_status_updated = pyqtSignal(int, int)  # 参数: tts队列长度, 音频队列长度

    def __init__(self, config_path: str = "config.ini"):
        super().__init__()

        # TTS生成队列 (优先级队列)
        self.tts_queue = queue.PriorityQueue()

        # 缓存数据
        self.cache_file = Path('data/tts_cache.json')
        self.tts_cache = {}  # 文本到音频路径的映射

        # 控制参数
        self.max_workers = 1  # GPT-SOVITS客户端内部有队列，这里只需要一个工作线程将任务提交给客户端
        self.running = False

        # 线程
        self.tts_thread = None
        self.monitor_thread = None

        # GPT-SOVITS客户端
        self.gptsovits_client = GPTSoVITSClient.get_instance(config_path)
        self.default_character = None # 默认角色信息

        # 加载缓存
        self._load_cache()

        # 获取默认角色信息
        self._load_default_character()

        logger.info("简化版TTSQueueManager已初始化")

    def _load_cache(self):
        """从文件加载缓存数据"""
        if not self.cache_file.exists():
            logger.info("未找到缓存文件")
            return

        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)

            # 只加载有效的缓存条目
            for key, path in cache_data.items():
                if os.path.exists(path):
                    self.tts_cache[key] = path

            logger.info(f"已加载 {len(self.tts_cache)} 条缓存记录")
        except Exception as e:
            logger.error(f"加载缓存失败: {e}")

    def _save_cache(self):
        """保存缓存数据到文件"""
        if not self.cache_file.parent.exists():
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            # 过滤掉无效的缓存条目
            valid_cache = {k: v for k, v in self.tts_cache.items() if os.path.exists(v)}

            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(valid_cache, f, ensure_ascii=False, indent=2)

            logger.info(f"已保存 {len(valid_cache)} 条缓存记录")
        except Exception as e:
            logger.error(f"保存缓存失败: {e}")

    def _load_default_character(self):
        """加载默认的GPT-SOVITS角色信息"""
        try:
            characters = self.gptsovits_client.list_characters()
            if characters:
                self.default_character = characters[0] # 使用第一个可用角色
                logger.info(f"已加载默认GPT-SOVITS角色: {self.default_character.get('name')}")
            else:
                logger.warning("未找到可用的GPT-SOVITS角色，请检查config.ini中的character_base_dir设置")
                self.default_character = None
        except Exception as e:
            logger.error(f"加载默认GPT-SOVITS角色失败: {e}", exc_info=True)
            self.default_character = None

    def start(self, start_audio_player=True):
        """启动队列处理

        Args:
            start_audio_player: 是否同时启动音频播放器
        """
        if self.running:
            logger.info("TTS队列管理器已在运行")
            return

        logger.info("启动TTS队列管理器")
        self.running = True

        # 启动TTS处理线程
        if self.tts_thread is None or not self.tts_thread.is_alive():
            self.tts_thread = threading.Thread(
                target=self._process_tts_queue,
                name="TTS_Queue_Processor"
            )
            self.tts_thread.daemon = True
            self.tts_thread.start()

        # 启动监控线程
        if self.monitor_thread is None or not self.monitor_thread.is_alive():
            self.monitor_thread = threading.Thread(
                target=self._monitor_status,
                name="TTS_Monitor"
            )
            self.monitor_thread.daemon = True
            self.monitor_thread.start()

    def stop(self):
        """停止队列处理"""
        if not self.running:
            return

        logger.info("停止TTS队列管理器")
        self.running = False

        # 清空队列
        while not self.tts_queue.empty():
            try:
                self.tts_queue.get_nowait()
                self.tts_queue.task_done()
            except queue.Empty:
                break

        # 保存缓存
        self._save_cache()

        # GPT-SOVITS客户端是单例，其生命周期由自身管理，无需在此显式停止

    def add_to_queue(self, text: str, item_id: str, is_priority: bool = False, use_cache: bool = True, product_name: str = "默认产品"):
        """添加文本到TTS队列

        Args:
            text: 要转换的文本内容
            item_id: 项目ID
            is_priority: 是否优先处理
            use_cache: 是否使用缓存
            product_name: 产品名称，用于音频文件存放路径
        """
        # 确保产品名称有效
        if not product_name or product_name.strip() == "":
            product_name = "默认产品"
            logger.warning(f"传入的产品名称为空，使用默认产品: {product_name}")

        # 生成缓存键 (包含产品名称，因为不同产品的同一文本可能使用不同角色)
        # 简化实现，缓存键只基于文本和默认说话人，如果需要按产品区分角色，缓存键需要包含产品信息
        speaker_id = self.default_character.get("name", "default_speaker") if self.default_character else "default_speaker"
        cache_key = hashlib.md5(f"{text}_{speaker_id}".encode()).hexdigest()

        # 检查缓存
        if use_cache and cache_key in self.tts_cache:
            cached_path = self.tts_cache[cache_key]
            if os.path.exists(cached_path):
                logger.info(f"使用缓存音频: {cached_path}")
                self.tts_completed.emit(item_id, cached_path)
                self.add_to_audio_queue(cached_path)
                return

        # 添加到TTS队列
        priority = Priority.HIGH if is_priority else Priority.NORMAL
        # 队列存储 (优先级, (item_id, text, cache_key, product_name))
        self.tts_queue.put((priority, (item_id, text, cache_key, product_name)))
        logger.info(f"添加文本到TTS队列: {item_id}, 产品: {product_name}, 优先级: {priority}, 队列长度: {self.tts_queue.qsize()}")

    def _monitor_status(self):
        """监控队列状态"""
        last_update = time.time()

        while self.running:
            try:
                current_time = time.time()

                # 每秒更新一次状态
                if current_time - last_update >= 1.0:
                    # 发送队列状态更新
                    tts_queue_size = self.tts_queue.qsize()
                    self.queue_status_updated.emit(tts_queue_size, 0) # 音频队列大小固定为0

                    last_update = current_time

                # 休眠
                time.sleep(0.5)

            except Exception as e:
                logger.error(f"状态监控错误: {e}")
                time.sleep(2.0)

    def _process_tts_queue(self):
        """处理TTS队列，将任务提交给GPT-SOVITS客户端"""
        logger.info("TTS队列处理线程已启动")
        while self.running:
            try:
                # 从队列获取任务 (阻塞模式)
                # 队列存储 (优先级, (item_id, text, cache_key, product_name))
                priority, (item_id, text, cache_key, product_name) = self.tts_queue.get()

                # 如果管理器停止运行，退出线程
                if not self.running:
                    break

                logger.info(f"从队列获取任务: {item_id}, 优先级: {priority}, 剩余队列长度: {self.tts_queue.qsize()}")

                # 发送开始信号
                self.tts_started.emit(item_id)

                # 调用GPT-SOVITS生成任务 (异步提交到客户端内部队列)
                self._generate_tts_task(text, item_id, cache_key, product_name)

                # 标记任务完成 (这里标记的是从SimpleTTSQueueManager队列中取出任务)
                self.tts_queue.task_done()

            except queue.Empty:
                # 队列为空时短暂休眠
                time.sleep(0.1)
            except Exception as e:
                logger.error(f"TTS队列处理错误: {e}", exc_info=True)
                time.sleep(1.0)

        logger.info("TTS队列处理线程已停止")


    def _generate_tts_task(self, text: str, item_id: str, cache_key: str, product_name: str):
        """TTS生成任务，调用GPT-SOVITS客户端"""
        try:
            # 定义回调函数
            def _gptsovits_callback(audio_data: Optional[bytes], error: Optional[str]):
                if audio_data:
                    try:
                        # 确保使用正确的产品路径
                        if not product_name or product_name.strip() == "":
                            current_product_name = "默认产品"
                            logger.warning(f"回调中产品名称为空，使用默认产品: {current_product_name}")
                        else:
                            current_product_name = product_name

                        # 创建输出目录
                        audio_dir = Path(f'data/products/{current_product_name}/audio')
                        audio_dir.mkdir(parents=True, exist_ok=True)

                        # 生成文件路径
                        timestamp = int(time.time() * 1000)
                        audio_path = str(audio_dir / f"{item_id}_{timestamp}.wav")

                        # 保存音频数据到文件
                        with open(audio_path, 'wb') as f:
                            f.write(audio_data)

                        logger.info(f"GPT-SOVITS音频生成完成并保存: {item_id}, 路径: {audio_path}")

                        # 添加到缓存
                        self.tts_cache[cache_key] = audio_path
                        self._save_cache() # 及时保存缓存

                        # 通知处理完成
                        self.tts_completed.emit(item_id, audio_path)

                        # 添加到播放队列 - Removed audio queue addition
                        # self.add_to_audio_queue(audio_path)

                    except Exception as e:
                        logger.error(f"处理GPT-SOVITS回调时发生错误: {e}", exc_info=True)
                        self.tts_failed.emit(item_id, f"处理回调失败: {str(e)}")
                else:
                    logger.error(f"GPT-SOVITS生成失败: {item_id}, 错误: {error}")
                    self.tts_failed.emit(item_id, f"TTS生成失败: {error}")

            # 获取角色参数
            if not self.default_character:
                logger.error("未找到可用的GPT-SOVITS角色，无法生成TTS")
                self.tts_failed.emit(item_id, "未找到可用的TTS角色")
                return

            params = {
                "ref_audio_path": self.default_character.get("ref_audio_path"),
                "ref_text": self.default_character.get("ref_text")
            }

            # 调用GPT-SOVITS客户端添加到队列
            self.gptsovits_client.queue_audio_request(
                text,
                params=params,
                callback=_gptsovits_callback
            )
            logger.info(f"已将请求 {item_id} 添加到GPT-SOVITS客户端队列")

        except Exception as e:
            logger.error(f"调用GPT-SOVITS客户端时发生错误: {e}", exc_info=True)
            self.tts_failed.emit(item_id, f"调用TTS客户端失败: {str(e)}")

    def add_to_audio_queue(self, audio_file_path: str):
        """添加音频文件到播放队列
        
        简化版本暂时不实现音频队列和播放器逻辑，
        实际项目中可以连接到AudioPlayer或其他播放组件。
        
        Args:
            audio_file_path: 音频文件路径
        """
        if not os.path.exists(audio_file_path):
            logger.warning(f"音频文件不存在: {audio_file_path}")
            return
        
        # 简化实现，仅记录日志
        logger.info(f"添加音频到播放队列: {audio_file_path}")
        # 在此可以添加实际的播放逻辑，或者发出信号通知播放器

    def add_llm_response_to_queue(self, text: str, response_id: str, product_name: str = "默认产品"):
        """添加LLM回复到TTS队列，设为高优先级

        Args:
            text: 回复文本
            response_id: 回复ID
            product_name: 产品名称
        """
        # 确保产品名称有效
        if not product_name or product_name.strip() == "":
            product_name = "默认产品"
            logger.warning(f"传入的产品名称为空，使用默认产品: {product_name}")

        # 添加到队列
        self.add_to_queue(text, response_id, is_priority=True, product_name=product_name)

# 导出需要的组件
TTSQueueManager = SimpleTTSQueueManager
