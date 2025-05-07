"""
音频播放器模块 - 播放TTS生成的音频
支持基本的音频播放功能，运行于独立线程中
"""

import os
import time
import logging
import threading
import wave
import queue
import numpy as np
from typing import Optional, Dict, Any, Callable
from PyQt6.QtCore import QObject, pyqtSignal, QThread, pyqtSlot

try:
    # 尝试导入音频库 (优先使用sounddevice)
    import sounddevice as sd
    AUDIO_BACKEND = "sounddevice"
except ImportError:
    try:
        # 备选方案：使用PyAudio
        import pyaudio
        AUDIO_BACKEND = "pyaudio"
    except ImportError:
        # 最后方案：使用模拟播放
        AUDIO_BACKEND = "mock"


class AudioPlayerWorker(QObject):
    """音频播放工作线程 - 在独立线程中运行以避免阻塞主线程"""
    # 定义信号
    playback_started = pyqtSignal(str)  # 播放开始信号(音频路径)
    playback_completed = pyqtSignal(str)  # 播放完成信号(音频路径)
    playback_error = pyqtSignal(str, str)  # 播放错误信号(音频路径, 错误消息)
    finished = pyqtSignal()  # 工作线程结束信号
    
    def __init__(self, log_handler=None):
        """初始化音频播放工作线程"""
        super().__init__()
        
        # 设置日志
        self.logger = logging.getLogger(self.__class__.__name__)
        if log_handler:
            self.logger.addHandler(log_handler)
            self.logger.setLevel(logging.INFO)
        
        # 状态变量
        self.is_playing = False
        self.running = False
        self.current_audio_path = None
        
        # 音频队列
        self.audio_queue = queue.Queue()
        
        # 线程锁
        self.lock = threading.Lock()
        
        # 音频后端
        self.logger.info(f"音频播放工作线程初始化，使用后端: {AUDIO_BACKEND}")
        
        # PyAudio实例 (如果使用PyAudio)
        self.pyaudio_instance = None
        if AUDIO_BACKEND == "pyaudio":
            self._init_pyaudio()
    
    @pyqtSlot()
    def process(self):
        """线程主循环 - 处理队列中的音频文件"""
        self.logger.info("音频播放工作线程已启动")
        self.running = True
        
        # PyAudio实例 (如果使用PyAudio)
        self.pyaudio_instance = None
        if AUDIO_BACKEND == "pyaudio":
            self._init_pyaudio()
        
        try:
            while self.running:
                try:
                    # 从队列中获取下一个音频文件（非阻塞）
                    try:
                        audio_path = self.audio_queue.get(block=True, timeout=0.5)
                    except queue.Empty:
                        continue
                    
                    # 播放音频
                    with self.lock:
                        self.is_playing = True
                        self.current_audio_path = audio_path
                    
                    # 执行播放
                    self._play_audio(audio_path)
                    
                    # 完成后重置状态
                    with self.lock:
                        self.is_playing = False
                        self.current_audio_path = None
                    
                    # 标记任务完成
                    self.audio_queue.task_done()
                    
                except Exception as e:
                    self.logger.error(f"处理音频队列时出错: {e}", exc_info=True)
                    time.sleep(0.5)  # 防止错误循环过快
        
        finally:
            # 清理资源
            self.cleanup()
            self.logger.info("音频播放工作线程已停止")
            self.finished.emit()
    
    def add_audio(self, audio_path: str):
        """添加音频文件到播放队列
        
        Args:
            audio_path: 音频文件路径
        """
        if not os.path.exists(audio_path):
            error_msg = f"音频文件不存在: {audio_path}"
            self.logger.error(error_msg)
            self.playback_error.emit(audio_path, error_msg)
            return False
        
        self.audio_queue.put(audio_path)
        self.logger.debug(f"已添加音频到播放队列: {audio_path}")
        return True
    
    def _init_pyaudio(self):
        """初始化PyAudio"""
        try:
            import pyaudio
            self.pyaudio_instance = pyaudio.PyAudio()
            self.logger.info("PyAudio实例初始化成功")
        except Exception as e:
            self.logger.error(f"初始化PyAudio失败: {e}", exc_info=True)
            self.pyaudio_instance = None
    
    def stop_current(self):
        """停止当前播放"""
        with self.lock:
            if not self.is_playing:
                return
            
            self.is_playing = False
            
            # 对于sounddevice后端
            if AUDIO_BACKEND == "sounddevice":
                try:
                    import sounddevice as sd
                    sd.stop()
                except Exception as e:
                    self.logger.error(f"停止sounddevice播放失败: {e}", exc_info=True)
            
            self.logger.info("停止当前音频播放")
    
    def stop(self):
        """停止工作线程并清空队列"""
        self.stop_current()  # 停止当前播放
        
        # 清空队列
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
                self.audio_queue.task_done()
            except queue.Empty:
                break
        
        # 设置停止标志
        self.running = False
    
    def _play_audio(self, audio_path: str) -> bool:
        """实际播放音频的方法
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            是否成功播放完成
        """
        self.logger.info(f"开始播放音频: {audio_path}")
        self.playback_started.emit(audio_path)
        
        try:
            if AUDIO_BACKEND == "sounddevice":
                success = self._play_with_sounddevice(audio_path)
            elif AUDIO_BACKEND == "pyaudio" and self.pyaudio_instance:
                success = self._play_with_pyaudio(audio_path)
            else:
                success = self._mock_play(audio_path)
            
            if success:
                self.logger.info(f"音频播放完成: {audio_path}")
                self.playback_completed.emit(audio_path)
            else:
                error_msg = "音频播放失败"
                self.logger.error(error_msg)
                self.playback_error.emit(audio_path, error_msg)
            
            return success
            
        except Exception as e:
            self.logger.error(f"播放音频时出错: {e}", exc_info=True)
            self.playback_error.emit(audio_path, str(e))
            return False
    
    def _play_with_sounddevice(self, audio_path: str) -> bool:
        """使用sounddevice播放WAV文件
        
        Args:
            audio_path: WAV文件路径
            
        Returns:
            是否成功播放
        """
        try:
            import sounddevice as sd
            
            # 读取WAV文件
            with wave.open(audio_path, 'rb') as wf:
                # 获取文件参数
                channels = wf.getnchannels()
                sample_width = wf.getsampwidth()
                sample_rate = wf.getframerate()
                frames = wf.readframes(wf.getnframes())
                
                # 转换为numpy数组
                if sample_width == 2:  # 16-bit
                    dtype = np.int16
                elif sample_width == 4:  # 32-bit
                    dtype = np.int32
                else:
                    dtype = np.int8
                
                audio_data = np.frombuffer(frames, dtype=dtype)
                
                # 立体声转换
                if channels == 2:
                    audio_data = audio_data.reshape(-1, 2)
                
                # 播放音频
                sd.play(audio_data, sample_rate)
                sd.wait()  # 等待播放完成
            
            return True
            
        except Exception as e:
            self.logger.error(f"使用sounddevice播放音频失败: {e}", exc_info=True)
            return False
    
    def _play_with_pyaudio(self, audio_path: str) -> bool:
        """使用PyAudio播放WAV文件
        
        Args:
            audio_path: WAV文件路径
            
        Returns:
            是否成功播放
        """
        try:
            import pyaudio
            
            # 确保PyAudio实例有效
            if not self.pyaudio_instance:
                self._init_pyaudio()
                if not self.pyaudio_instance:
                    return False
            
            # 打开WAV文件
            with wave.open(audio_path, 'rb') as wf:
                # 创建音频流
                stream = self.pyaudio_instance.open(
                    format=self.pyaudio_instance.get_format_from_width(wf.getsampwidth()),
                    channels=wf.getnchannels(),
                    rate=wf.getframerate(),
                    output=True
                )
                
                # 读取数据并播放
                chunk_size = 1024
                data = wf.readframes(chunk_size)
                
                while data and self.is_playing:
                    stream.write(data)
                    data = wf.readframes(chunk_size)
                
                # 停止并关闭流
                stream.stop_stream()
                stream.close()
            
            return True
            
        except Exception as e:
            self.logger.error(f"使用PyAudio播放音频失败: {e}", exc_info=True)
            return False
    
    def _mock_play(self, audio_path: str) -> bool:
        """模拟播放音频
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            是否成功播放
        """
        try:
            # 读取WAV文件头部以获取持续时间
            with wave.open(audio_path, 'rb') as wf:
                # 计算播放时间 (秒)
                frames = wf.getnframes()
                rate = wf.getframerate()
                duration = frames / float(rate)
            
            self.logger.info(f"模拟播放音频: {audio_path}, 持续: {duration:.2f}秒")
            
            # 模拟播放，每0.1秒检查一次是否需要停止
            end_time = time.time() + duration
            while time.time() < end_time and self.is_playing:
                time.sleep(0.1)
            
            return True
            
        except Exception as e:
            self.logger.error(f"模拟播放音频失败: {e}", exc_info=True)
            return False
    
    # 删除重复的stop方法，由于上面已经有stop_current和stop两个方法，这个是多余的
    
    def cleanup(self):
        """清理资源"""
        self.stop_current()
        
        # 清理PyAudio实例
        if AUDIO_BACKEND == "pyaudio" and self.pyaudio_instance:
            try:
                self.pyaudio_instance.terminate()
                self.pyaudio_instance = None
            except Exception as e:
                self.logger.error(f"清理PyAudio实例失败: {e}", exc_info=True)
        
        self.logger.info("音频播放器资源清理完成")


class AudioPlayer(QObject):
    """音频播放器 - 管理在独立线程中运行的音频播放工作器"""
    # 定义信号 - 转发工作线程的信号
    playback_started = pyqtSignal(str)  # 播放开始信号(音频路径)
    playback_completed = pyqtSignal(str)  # 播放完成信号(音频路径)
    playback_error = pyqtSignal(str, str)  # 播放错误信号(音频路径, 错误消息)
    
    def __init__(self):
        """初始化音频播放器"""
        super().__init__()
        
        # 设置日志
        self.logger = logging.getLogger(self.__class__.__name__)
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        
        # 创建工作线程
        self.worker_thread = QThread()
        self.worker = AudioPlayerWorker(log_handler=handler)
        self.worker.moveToThread(self.worker_thread)
        
        # 连接信号
        self.worker_thread.started.connect(self.worker.process)
        self.worker.finished.connect(self.worker_thread.quit)
        
        # 转发信号
        self.worker.playback_started.connect(self.playback_started)
        self.worker.playback_completed.connect(self.playback_completed)
        self.worker.playback_error.connect(self.playback_error)
        
        # 启动工作线程
        self.worker_thread.start()
        
        self.logger.info("音频播放器初始化完成，工作线程已启动")
    
    def play(self, audio_path: str, blocking: bool = False) -> bool:
        """播放音频文件（异步或同步）
        
        Args:
            audio_path: 音频文件路径
            blocking: 是否阻塞等待播放完成 (保留参数，但在线程模式下总是非阻塞)
            
        Returns:
            是否成功添加到播放队列
        """
        # 检查文件是否存在
        if not os.path.exists(audio_path):
            error_msg = f"音频文件不存在: {audio_path}"
            self.logger.error(error_msg)
            self.playback_error.emit(audio_path, error_msg)
            return False
        
        # 检查文件类型
        if not audio_path.lower().endswith('.wav'):
            error_msg = f"不支持的音频格式: {audio_path}"
            self.logger.error(error_msg)
            self.playback_error.emit(audio_path, error_msg)
            return False
        
        # 添加到工作线程队列
        return self.worker.add_audio(audio_path)
    
    def stop(self):
        """停止当前播放并清空队列"""
        self.worker.stop_current()
    
    def cleanup(self):
        """清理资源并停止工作线程"""
        self.logger.info("关闭音频播放器和工作线程...")
        
        # 停止工作线程
        if self.worker_thread.isRunning():
            self.worker.stop()
            if not self.worker_thread.wait(1000):  # 等待最多1秒
                self.worker_thread.terminate()
        
        self.logger.info("音频播放器资源清理完成")
    
    def is_playing(self) -> bool:
        """检查是否有音频正在播放
        
        Returns:
            是否有音频正在播放
        """
        return self.worker.is_playing
