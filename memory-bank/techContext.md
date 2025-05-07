# 抖音电商无人直播系统 - 技术上下文

## 核心技术栈
- **语言**: Python 3.9+
- **UI框架**: PyQt6
- **LLM集成**: Volcengine API, Ollama
- **通信协议**: WebSocket, HTTP, **Redis Pub/Sub**
- **语音合成**: GPT-SoVITS
- **音频处理**: numpy, PyTorch, webrtcvad, pygame
- **数据存储**: SQLite, JSON
- **并发处理**: threading, concurrent.futures, asyncio, QThread
- **日志系统**: Python logging

## 开发环境
- **IDE**: Visual Studio Code
- **版本控制**: Git
- **构建工具**: PyInstaller (最终打包)
- **依赖管理**: pip, requirements.txt
- **测试框架**: pytest
- **代码风格**: PEP 8, flake8

## 关键依赖
```
pyqt6==6.5.0
websockets==10.4
numpy==1.23.5
torch==2.0.1
requests==2.28.2
pydub==0.25.1
pyaudio==0.2.13
webrtcvad==2.0.10
pygame==2.1.2
volcenginesdkarkruntime==0.1.6  # 火山引擎API
```

## 技术约束
1. **PyQt线程限制**:
   - UI操作必须在主线程进行
   - 长时间操作需要放在工作线程中
   - 使用信号槽机制在线程间通信
   - LLM请求操作使用QThread避免UI冻结

2. **LLM集成约束**:
   - 火山引擎API需要有效的API密钥和区域配置
   - Ollama需要本地部署和启动服务
   - 请求超时处理和错误恢复
   - 处理不同模型输出格式差异
   - 火山引擎API调用频率限制

3. **TTS系统要求**:
   - GPT-SoVITS API需要本地部署或网络访问
   - 支持中文、普通话生成
   - 需有足够计算资源支持实时TTS
   - 处理VAD检测、重试和模型轮换
   - 支持优先级打断和音频分块处理

4. **WebSocket连接**:
   - 需保持长连接
   - 处理不稳定网络环境
   - 实现自动重连机制
   - 支持心跳检测维持连接

5. **资源限制**:
   - 内存占用控制在合理范围
   - CPU使用率平衡
   - 音频缓存大小限制
   - LLM请求并发控制
   - 优化大量消息处理场景的性能

6. **变体模板语法约束**:
   - 使用"{选项1|选项2}"格式标记变体
   - 支持嵌套变体处理
   - 变体内不应包含段落分隔符

## 技术决策
1. **使用PyQt6而非Web技术**:
   - 降低部署复杂度
   - 更好的桌面集成
   - 更高效的本地资源利用

2. **采用SQLite而非大型数据库**:
   - 简化部署和配置
   - 满足当前数据存储需求
   - 零配置、嵌入式

3. **使用 Redis Pub/Sub 作为消息队列**:
   - 轻量级、易于集成
   - 支持发布/订阅模式，适合模块间松耦合通信
   - 符合项目对简化部署的偏好

3. **多线程与异步结合**:
   - UI响应使用Qt事件循环
   - WebSocket通信使用asyncio
   - TTS处理使用多线程池
   - LLM请求使用QThread

4. **本地音频缓存策略**:
   - 使用LRU策略管理缓存
   - 基于MD5哈希进行音频索引
   - 定期清理过期缓存

5. **LLM集成策略**:
   - 支持本地Ollama和云端火山引擎双通道
   - 统一接口设计，便于切换模型
   - 实现流式生成增强用户体验
   - 异步处理避免UI阻塞

6. **变体模板系统**:
   - 采用"{选项1|选项2}"格式作为标准语法
   - 基于GPT模型生成变体标记
   - 分离基础话术与变体模板存储
   - 文件系统而非数据库存储话术和模板

## TTS质量控制技术

### 1. VAD技术集成
1. **webrtcvad库集成**:
   - 使用Google的开源语音活动检测库
   - 支持四种敏感度模式(0-3)
   - 实现音频帧级别的语音检测
   - 使用模式3提供最高灵敏度

2. **备用能量检测**:
   - 当webrtcvad不可用时自动切换
   - 基于音频样本能量计算
   - 设置自适应阈值区分语音和静音
   - 通过样本绝对值平均值评估音频能量

3. **实现细节**:
   ```python
   def is_silence(self, audio_data: bytes, sample_rate: int = 24000) -> bool:
       """检测音频是否为静音或无声"""
       if self.vad:
           # 使用webrtcvad进行检测
           frame_size = int(target_rate * 0.03 * 2)  # 16k采样率，30ms，16bit
           frames = [resampled_data[i:i+frame_size] for i in range(0, len(resampled_data)-frame_size, frame_size)]
           voiced_frames = sum(1 for frame in frames if self.vad.is_speech(frame, target_rate))
           voiced_ratio = voiced_frames / len(frames) if frames else 0
           return voiced_ratio < 0.1  # 有声帧比例小于10%认为是静音
       else:
           # 备用能量检测方法
           return self._energy_detection(audio_data)
   ```

### 2. 非阻塞VAD检测设计
1. **线程池处理**:
   - 使用`concurrent.futures.ThreadPoolExecutor`
   - VAD检测在工作线程执行避免阻塞
   - 通过回调函数处理检测结果
   - 维护固定大小线程池优化资源使用

2. **处理过程分离**:
   - TTS生成与VAD检测分离
   - 检测结果通过回调或信号通知
   - 支持多种后续处理策略
   - 失败时可选择不同处理路径

3. **实现方案**:
   ```python
   def process_tts_result(self, audio_data, item_id):
       """处理TTS生成结果"""
       # 提交VAD检测任务到线程池
       future = self.executor.submit(self.vad_detector.is_silence, audio_data)
       # 添加回调处理检测结果
       future.add_done_callback(
           lambda f: self._handle_vad_result(f.result(), audio_data, item_id)
       )
   ```

### 3. 多模型轮换策略
1. **模型定义和选择**:
   - 配置多个TTS模型变体
   - 基于文本内容和失败历史选择模型
   - 支持模型优先级排序
   - 维护模型成功率统计

2. **轮换实现**:
   ```python
   def _select_tts_model(self, text, attempt=0):
       """为文本选择合适的TTS模型"""
       models = [
           {"id": "default", "speaker_id": "speaker1", "weight": 1.0},
           {"id": "alternative1", "speaker_id": "speaker2", "weight": 0.8},
           {"id": "alternative2", "speaker_id": "speaker3", "weight": 0.6}
       ]
       
       # 简单轮换策略
       if attempt < len(models):
           return models[attempt]
           
       # 随机选择一个备选模型
       import random
       weighted_models = [(m["id"], m["weight"]) for m in models]
       model_ids, weights = zip(*weighted_models)
       return next(m for m in models if m["id"] == random.choices(model_ids, weights=weights)[0])
   ```

3. **递进式重试**:
   - 初次尝试使用默认模型
   - 第一次失败换用不同参数的模型
   - 后续失败尝试不同角色ID
   - 最后尝试降级参数集（简化文本等）

### 4. 中间件架构
1. **前处理中间件**:
   - 文本规范化（移除特殊字符）
   - 文本分段（基于句子结构）
   - 添加角色相关前缀或后缀
   - 特殊符号处理（数字、符号朗读等）

2. **后处理中间件**:
   - VAD检测
   - 音频标准化（调整音量）
   - 静音删除（首尾静音）
   - 特效应用（背景音乐混合等）

3. **管道实现**:
   ```python
   class TTSMiddlewarePipeline:
       """TTS中间件处理管道"""
       
       def __init__(self):
           self.pre_processors = []
           self.post_processors = []
           
       def add_pre_processor(self, processor):
           self.pre_processors.append(processor)
           
       def add_post_processor(self, processor):
           self.post_processors.append(processor)
           
       def process_text(self, text, context=None):
           """处理文本"""
           result = text
           ctx = context or {}
           
           for processor in self.pre_processors:
               result = processor(result, ctx)
               
           return result, ctx
           
       def process_audio(self, audio_data, context=None):
           """处理音频"""
           result = audio_data
           ctx = context or {}
           
           for processor in self.post_processors:
               result = processor(result, ctx)
               
           return result, ctx
   ```

## 音频播放与优先级处理技术

### 1. 分块音频播放技术
1. **块设计**:
   - 固定大小块（4096字节）
   - 保留WAV头信息在第一块
   - 内存中块队列管理
   - 支持块级别中断

2. **块切分实现**:
   ```python
   def _split_audio(self, audio_data: bytes) -> List[bytes]:
       """将音频数据分割为块"""
       # 处理WAV头
       wav_header = None
       data = audio_data
       
       if len(audio_data) > 44 and audio_data.startswith(b'RIFF') and b'WAVE' in audio_data[0:12]:
           wav_header = audio_data[0:44]
           data = audio_data[44:]
           
       # 分块处理
       chunks = []
       for i in range(0, len(data), self.chunk_size):
           chunk = data[i:i+self.chunk_size]
           if i == 0 and wav_header:  # 第一块加上WAV头
               chunks.append(wav_header + chunk)
           else:
               chunks.append(chunk)
                   
       return chunks
   ```

3. **播放调度**:
   - 块队列按优先级排序
   - 单线程顺序播放块
   - 支持块间暂停和中断
   - 通过回调通知状态变化

### 2. 播放状态管理
1. **状态定义**:
   - 空闲(Idle)：无音频播放
   - 播放中(Playing)：正在播放音频
   - 已中断(Interrupted)：当前播放被高优先级任务中断
   - 中断决策(InterruptDecision)：决定是否中断当前播放
   - 中断后处理(PostInterrupt)：处理中断后的恢复或丢弃

2. **状态转换**:
   - Idle → Playing：收到音频开始播放
   - Playing → InterruptDecision：收到高优先级音频
   - InterruptDecision → Interrupted：决定中断当前播放
   - Interrupted → Playing：恢复被中断的播放
   - Playing → Idle：播放完成

3. **状态机实现**:
   ```python
   class AudioPlayerState(Enum):
       IDLE = "idle"
       PLAYING = "playing"
       INTERRUPT_DECISION = "interrupt_decision"
       INTERRUPTED = "interrupted"
       POST_INTERRUPT = "post_interrupt"
   
   class AudioPlayerStateMachine:
       def __init__(self):
           self.state = AudioPlayerState.IDLE
           self.current_task = None
           self.interrupted_task = None
           
       def transition(self, event, **kwargs):
           """处理状态转换"""
           if self.state == AudioPlayerState.IDLE:
               if event == "start_playback":
                   self.current_task = kwargs.get("task")
                   self.state = AudioPlayerState.PLAYING
                   return True
                   
           elif self.state == AudioPlayerState.PLAYING:
               if event == "playback_complete":
                   self.current_task = None
                   self.state = AudioPlayerState.IDLE
                   return True
               elif event == "high_priority_task":
                   self.state = AudioPlayerState.INTERRUPT_DECISION
                   return self._handle_interrupt_decision(kwargs.get("task"))
                   
           # 其他状态转换逻辑...
           
           return False
   ```

### 3. 优先级控制技术
1. **细粒度优先级定义**:
   ```python
   class Priority:
       """定义队列优先级常量"""
       EMERGENCY = -10    # 系统通知、错误恢复
       GIFT_LARGE = -5    # 大额礼物
       USER_VIP = -2      # VIP用户评论
       GIFT_NORMAL = -1   # 普通礼物
       COMMENT_IMPORTANT = 0  # 重要评论(关键词)
       NORMAL = 5         # 普通互动评论
       SCRIPT = 10        # 预设话术
       BACKGROUND = 20    # 背景音乐等
   ```

2. **优先级队列实现**:
   - 使用Python标准库`queue.PriorityQueue`
   - 队列项支持`__lt__`方法实现排序
   - 三元组结构:(优先级, 创建时间, 数据)
   - 支持按优先级和时间排序

3. **动态优先级计算**:
   ```python
   def calculate_priority(message_type, user_info, content, system_state):
       """动态计算消息优先级"""
       base_priority = Priority.NORMAL
       
       # 基于消息类型
       if message_type == "gift":
           coin_value = user_info.get("coin_value", 0)
           if coin_value > 1000:
               base_priority = Priority.GIFT_LARGE
           else:
               base_priority = Priority.GIFT_NORMAL
       elif message_type == "comment":
           if any(kw in content for kw in IMPORTANT_KEYWORDS):
               base_priority = Priority.COMMENT_IMPORTANT
               
       # 用户因素
       user_level = user_info.get("level", 0)
       level_bonus = min(user_level // 10, 3)  # 最多-3的优先级提升
       
       # 活跃度因素
       activity_score = user_info.get("activity_score", 0)
       activity_bonus = min(activity_score // 100, 2)  # 最多-2的优先级提升
       
       # 系统状态调整
       if system_state.get("is_idle", False):
           # 如果系统空闲，可以略微提高优先级
           idle_bonus = 1
       else:
           idle_bonus = 0
           
       # 最终优先级（数字越小优先级越高）
       final_priority = base_priority - level_bonus - activity_bonus - idle_bonus
       
       return final_priority
   ```

### 4. 中断与恢复策略
1. **中断决策算法**:
   - 优先级差距评估
   - 当前任务已完成比例
   - 用户体验连续性考虑
   - 系统负载因素

2. **恢复机制**:
   - 记忆中断位置
   - 保存中断任务状态
   - 支持自动恢复或丢弃
   - 中断任务优先级动态调整

3. **实现示例**:
   ```python
   def _handle_interrupt_decision(self, new_task):
       """处理中断决策"""
       # 获取当前任务和新任务信息
       current_priority = self.current_task[1]
       current_progress = self.current_task[3]  # 已播放的百分比
       new_priority = new_task[1]
       
       # 优先级差距
       priority_diff = current_priority - new_priority
       
       # 基本规则：优先级差距大于等于5时中断
       should_interrupt = priority_diff >= 5
       
       # 动态调整：接近完成的任务不易被中断
       if current_progress > 0.85:  # 已完成85%以上
           should_interrupt = priority_diff >= 8  # 需要更大差距才中断
           
       if should_interrupt:
           self.interrupted_task = self.current_task
           self.current_task = new_task
           self.state = AudioPlayerState.INTERRUPTED
           return True
       else:
           # 不中断，将新任务加入队列前端
           self.task_queue.put((new_priority, time.time(), new_task))
           self.state = AudioPlayerState.PLAYING
           return False
   ```

## 开发工具配置
1. **VSCode扩展**:
   - Python
   - PyQt Integration
   - SQLite Viewer
   - GitLens
   - Python Test Explorer

2. **Python环境**:
   - 使用venv或conda创建隔离环境
   - 固定依赖版本避免兼容性问题

3. **调试配置**:
   - PyQt远程调试支持
   - 日志级别可动态调整
   - 支持实时监控系统状态

## 部署与运行
1. **部署方式**:
   - 独立可执行文件(PyInstaller打包)
   - 可选Docker容器化

2. **运行要求**:
   - Windows 10/11 或 Linux
   - 最小8GB RAM
   - 支持OpenGL的显卡
   - 稳定网络连接

3. **配置管理**:
   - 使用INI格式外部配置文件
   - 支持运行时部分配置热更新
   - 敏感配置加密存储

## GPT-SoVITS集成技术

### 1. API客户端设计
1. **客户端接口**:
   ```python
   class GPTSoVITSClient:
       @staticmethod
       def get_instance(config_path=None):
           """获取单例实例"""
           pass
           
       def test_connection(self):
           """测试API连接"""
           pass
           
       def list_characters(self):
           """获取可用角色列表"""
           pass
           
       def generate_audio(self, text, tts_params):
           """同步生成音频"""
           pass
           
       def queue_audio_request(self, text, tts_params, callback):
           """异步排队生成音频"""
           pass
   ```

2. **异步请求处理**:
   - 使用线程池并行处理请求
   - 支持同步和异步模式
   - 通过回调通知请求完成
   - 实现请求队列和优先级

3. **错误处理与重试**:
   - 超时处理(默认10秒)
   - 网络错误自动重试
   - API错误分类与处理
   - 降级方案实现

### 2. 音频缓存与优化
1. **缓存机制**:
   ```python
   def get_cache_key(self, text, character_id):
       """获取缓存键"""
       import hashlib
       key_str = f"{text}_{character_id}"
       return hashlib.md5(key_str.encode('utf-8')).hexdigest()
   ```

2. **缓存策略**:
   - LRU(最近最少使用)淘汰策略
   - 基于时间戳的过期清理
   - 缓存大小限制控制
   - 定期自动清理

3. **磁盘存储优化**:
   - 按产品和ID组织文件目录
   - 时间戳确保文件名唯一
   - 定期清理临时文件
   - 大小限制和配额管理

## 音频处理技术

### 1. 音频标准化
1. **音量标准化**:
   ```python
   def normalize_audio(audio_data, target_db=-20):
       """标准化音频音量"""
       import numpy as np
       
       # 将字节数据转换为浮点数组
       samples = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
       
       # 计算当前RMS值
       rms = np.sqrt(np.mean(samples**2))
       if rms < 1e-8:  # 防止除零错误
           return audio_data
           
       # 计算当前dB
       current_db = 20 * np.log10(rms)
       
       # 计算增益
       gain = 10**((target_db - current_db) / 20)
       
       # 应用增益
       normalized_samples = samples * gain
       
       # 剪裁防止过载
       normalized_samples = np.clip(normalized_samples, -1.0, 1.0)
       
       # 转回16位整数
       normalized_samples = (normalized_samples * 32767).astype(np.int16)
       
       return normalized_samples.tobytes()
   ```

2. **静音删除**:
   - 检测首尾静音段
   - 计算帧能量阈值
   - 动态调整检测敏感度
   - 保留最小静音长度

3. **格式转换**:
   - WAV格式处理与生成
   - 采样率转换支持
   - 单声道和双声道处理
   - PCM格式标准化

### 2. pygame音频播放
1. **初始化与配置**:
   ```python
   def init_audio_system(sample_rate=24000, buffer_size=4096):
       """初始化音频系统"""
       import pygame
       
       # 完整初始化以避免视频系统未初始化错误
       pygame.init()
       
       # 初始化混音器
       pygame.mixer.init(
           frequency=sample_rate,
           size=-16,  # 有符号16位
           channels=1,  # 单声道
           buffer=buffer_size
       )
       
       return pygame.mixer
   ```

2. **音频播放控制**:
   - 音频播放状态监测
   - 播放完成事件处理
   - 播放暂停与恢复
   - 音量控制与淡入淡出

3. **备用播放机制**:
   - 检测pygame可用性
   - 提供模拟播放方案
   - 基于音频长度计时
   - 状态同步与通知

## 并发与线程安全

### 1. 线程池管理
1. **线程池配置**:
   ```python
   def create_thread_pool(max_workers=3, thread_name_prefix="Worker"):
       """创建线程池"""
       import concurrent.futures
       
       return concurrent.futures.ThreadPoolExecutor(
           max_workers=max_workers,
           thread_name_prefix=thread_name_prefix
       )
   ```

2. **任务提交与处理**:
   - 支持返回Future对象
   - 添加完成回调函数
   - 实现任务取消机制
   - 异常处理与传播

3. **资源控制**:
   - 限制最大线程数
   - 使用信号量控制并发
   - 动态调整工作线程
   - 优雅关闭与资源释放

### 2. 线程安全机制
1. **锁与同步**:
   ```python
   class ThreadSafeResource:
       """线程安全资源类"""
       
       def __init__(self, value=None):
           self.value = value
           self.lock = threading.RLock()
           
       def get(self):
           """获取资源"""
           with self.lock:
               return self.value
               
       def update(self, new_value):
           """更新资源"""
           with self.lock:
               old_value = self.value
               self.value = new_value
               return old_value
   ```

2. **跨线程通信**:
   - PyQt信号槽机制
   - 线程安全队列
   - 事件通知机制
   - 原子操作优化

3. **线程生命周期管理**:
   - 优雅启动与停止
   - 守护线程配置
   - 线程状态监控
   - 资源清理与回收

## 队列系统技术

### 1. 优先级队列实现
1. **多级队列设计**:
   ```python
   class MultiLevelQueue:
       """多级优先级队列"""
       
       def __init__(self, levels=3):
           """初始化多级队列"""
           self.queues = [queue.Queue() for _ in range(levels)]
           self.lock = threading.RLock()
           
       def put(self, item, priority=1):
           """添加项目到队列"""
           with self.lock:
               # 确保优先级在有效范围内
               level = max(0, min(priority, len(self.queues) - 1))
               self.queues[level].put(item)
               
       def get(self):
           """获取最高优先级项目"""
           with self.lock:
               # 从高优先级队列开始检查
               for q in self.queues:
                   if not q.empty():
                       return q.get()
               
               # 所有队列为空
               raise queue.Empty()
   ```

2. **调度策略**:
   - 严格优先级调度
   - 带有饥饿防止的加权调度
   - 动态优先级调整
   - 超时与到期处理

3. **队列监控**:
   - 队列长度监控
   - 阻塞时间统计
   - 吞吐量测量
   - 调度公平性分析

### 2. 生产者消费者模式
1. **生产者设计**:
   - 支持多生产者并发添加
   - 实现背压机制控制生产速率
   - 生产限制与节流
   - 优先级生产处理

2. **消费者设计**:
   - 多消费者并行处理
   - 批处理优化吞吐量
   - 处理失败重试机制
   - 异常检测与处理

3. **协调机制**:
   - 阻塞与非阻塞模式
   - 条件变量通知
   - 任务取消与中断
   - 优雅关闭处理

## 监控与调试技术

### 1. 日志系统
1. **分级日志设计**:
   ```python
   def setup_logging(log_dir="data/logs", log_level=logging.INFO):
       """设置日志系统"""
       import logging.handlers
       import os
       
       # 确保日志目录存在
       os.makedirs(log_dir, exist_
