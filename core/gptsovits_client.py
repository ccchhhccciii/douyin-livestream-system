"""GPT-SOVITS TTS 客户端 - 负责与GPT-SOVITS API 交互生成音频"""
import os
import json
import logging
import configparser
import requests
import time
from queue import Queue
from threading import Lock, Thread
from typing import Dict, Any, Optional, Union, Tuple, List, Callable

# 配置日志
logger = logging.getLogger(__name__)

# 单例实例存储
_instance = None
_instance_lock = Lock()

class GPTSoVITSClient:
    """GPT-SOVITS TTS 客户端 - 用于调用 GPT-SOVITS API 生成音频 (单例模式)"""
    
    @classmethod
    def get_instance(cls, config_path: str = "config.ini") -> 'GPTSoVITSClient':
        """获取单例实例
        
        Args:
            config_path: 配置文件路径
            
        Returns:
            GPTSoVITSClient: 单例实例
        """
        global _instance
        with _instance_lock:
            if _instance is None:
                logger.info("创建GPTSoVITSClient单例实例")
                _instance = cls(config_path)
            return _instance
    def __init__(self, config_path: str = "config.ini"):
        """初始化 GPT-SOVITS 客户端 (通常不应直接调用，请使用get_instance方法)"""
        """初始化 GPT-SOVITS 客户端
        
        Args:
            config_path: 配置文件路径，包含 API 相关配置
        """
        self.api_base_url = "http://127.0.0.1:9880"  # 默认API基础URL
        self.character_base_dir = ""  # 角色根目录
        self.timeout = 120  # 请求超时时间（秒）
        
        # 请求控制参数
        self.request_queue = Queue()  # 请求队列
        self.request_lock = Lock()    # 请求锁
        self.is_processing = False    # 是否正在处理请求
        self.request_interval = 2.0   # 请求间隔时间（秒）
        self.max_retries = 3          # 最大重试次数
        self.worker_thread = None     # 工作线程
        self.callbacks = {}           # 回调函数字典
        
        # 尝试从配置文件加载设置
        self._load_config(config_path)
        
        # 启动工作线程
        self._start_worker()
        
        logger.info(f"GPT-SOVITS客户端已初始化，API基础URL: {self.api_base_url}, 请求间隔: {self.request_interval}秒")
    
    def _load_config(self, config_path: str):
        """从配置文件加载设置
        
        Args:
            config_path: 配置文件路径
        """
        try:
            if not os.path.exists(config_path):
                logger.warning(f"配置文件不存在: {config_path}，使用默认配置")
                return
                
            config = configparser.ConfigParser()
            config.read(config_path, encoding='utf-8')
            
            if 'TTS' in config:
                if 'api_base_url' in config['TTS']:
                    self.api_base_url = config['TTS'].get('api_base_url')
                    logger.info(f"从配置文件加载 API 基础 URL: {self.api_base_url}")
                    
                if 'character_base_dir' in config['TTS']:
                    self.character_base_dir = config['TTS'].get('character_base_dir')
                    logger.info(f"从配置文件加载角色根目录: {self.character_base_dir}")
                    
                if 'timeout' in config['TTS']:
                    self.timeout = config['TTS'].getint('timeout', 120)
                    logger.info(f"从配置文件加载请求超时时间: {self.timeout}秒")
                
                # 加载请求控制参数
                if 'request_interval' in config['TTS']:
                    try:
                        self.request_interval = config['TTS'].getfloat('request_interval', 2.0)
                    except ValueError:
                        # 尝试处理可能包含注释的值
                        interval_str = config['TTS']['request_interval'].split('#')[0].strip()
                        try:
                            self.request_interval = float(interval_str)
                        except ValueError:
                            logger.warning(f"无法解析请求间隔时间: {config['TTS']['request_interval']}，使用默认值: 2.0秒")
                            self.request_interval = 2.0
                    logger.info(f"从配置文件加载请求间隔时间: {self.request_interval}秒")
                
                if 'max_retries' in config['TTS']:
                    try:
                        self.max_retries = config['TTS'].getint('max_retries', 3)
                    except ValueError:
                        # 尝试处理可能包含注释的值
                        retries_str = config['TTS']['max_retries'].split('#')[0].strip()
                        try:
                            self.max_retries = int(retries_str)
                        except ValueError:
                            logger.warning(f"无法解析最大重试次数: {config['TTS']['max_retries']}，使用默认值: 3")
                            self.max_retries = 3
                    logger.info(f"从配置文件加载最大重试次数: {self.max_retries}")
                    
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}", exc_info=True)
    
    def _start_worker(self):
        """启动工作线程处理队列中的请求 - 严格串行执行"""
        def worker():
            logger.info("TTS请求处理线程已启动 - 严格串行模式")
            while True:
                try:
                    # 获取请求（阻塞模式）
                    request_id, text, params, callback = self.request_queue.get()
                    if request_id is None:  # 停止信号
                        logger.info("收到停止信号，TTS请求处理线程将退出")
                        break
                        
                    logger.info(f"开始处理请求 ID: {request_id}, 剩余队列长度: {self.request_queue.qsize()}")
                    
                    # 添加API请求锁，确保同一时间只有一个API请求在处理
                    with self.request_lock:
                        # 处理请求（带重试）
                        result = None
                        error = None
                        for retry in range(self.max_retries + 1):
                            if retry > 0:
                                logger.info(f"重试请求 ID: {request_id} (第 {retry}/{self.max_retries} 次)")
                                # 重试前等待时间递增
                                time.sleep(self.request_interval * (1 + retry * 0.5))
                            
                            try:
                                logger.info(f"发送API请求: {request_id}")
                                result = self._generate_audio(text, params)
                                if result:
                                    logger.info(f"请求 ID: {request_id} 处理成功，音频大小: {len(result)} 字节")
                                    error = None
                                    break
                                else:
                                    error = "TTS生成失败，未返回有效音频数据"
                                    logger.warning(f"请求 ID: {request_id} 处理失败: {error}")
                            except Exception as e:
                                error = str(e)
                                logger.error(f"请求 ID: {request_id} 处理异常: {error}", exc_info=True)
                    
                    # 执行回调
                    if callback:
                        try:
                            logger.info(f"执行回调函数: {request_id}")
                            callback(result, error)
                        except Exception as cb_error:
                            logger.error(f"执行回调函数出错: {cb_error}", exc_info=True)
                    
                    # 标记任务完成
                    self.request_queue.task_done()
                    
                    # 在处理下一个请求前等待固定时间，避免API过载
                    wait_time = self.request_interval * 2 if error else self.request_interval
                    logger.info(f"请求 {request_id} 处理完成，等待 {wait_time} 秒后处理下一个请求")
                    time.sleep(wait_time)
                    
                except Exception as e:
                    logger.error(f"TTS请求处理线程发生异常: {e}", exc_info=True)
        
        # 创建并启动工作线程
        self.worker_thread = Thread(target=worker, daemon=True)
        self.worker_thread.start()
    
    def queue_audio_request(self, text: str, params: Dict[str, Any] = None, 
                           callback: Callable[[Optional[bytes], Optional[str]], None] = None) -> str:
        """将音频生成请求添加到队列
        
        Args:
            text: 要合成的文本
            params: 合成参数
            callback: 回调函数，接收两个参数: (音频数据, 错误信息)
            
        Returns:
            str: 请求ID
        """
        if not text or not text.strip():
            logger.warning("输入文本为空，无法添加到请求队列")
            if callback:
                callback(None, "输入文本为空")
            return ""
        
        # 生成请求ID
        import uuid
        request_id = str(uuid.uuid4())
        
        # 将请求添加到队列
        self.request_queue.put((request_id, text, params, callback))
        logger.info(f"音频请求已添加到队列，ID: {request_id}, 当前队列长度: {self.request_queue.qsize()}")
        
        return request_id
    
    def generate_audio(self, text: str, params: Dict[str, Any] = None) -> Optional[bytes]:
        """生成音频（同步模式，不推荐使用）
        
        注意：此方法直接发送请求，不使用请求队列。不推荐在生产环境中使用，
        可能导致TTS服务器过载。推荐使用queue_audio_request方法。
        
        Args:
            text: 要合成的文本
            params: 合成参数
            
        Returns:
            bytes: 生成的音频数据（WAV格式），失败则返回None
        """
        logger.warning("直接调用generate_audio方法可能导致TTS服务器过载，推荐使用queue_audio_request")
        return self._generate_audio(text, params)
    
    def _generate_audio(self, text: str, params: Dict[str, Any] = None) -> Optional[bytes]:
        """实际生成音频的内部方法
        
        Args:
            text: 要合成的文本
            params: 合成参数，包括参考音频路径、参考文本等
            
        Returns:
            bytes: 生成的音频数据（WAV格式），失败则返回 None
        """
        if not text or not text.strip():
            logger.warning("输入文本为空，无法生成音频")
            return None
        
        # 提取参数
        ref_audio_path = params.get('ref_audio_path', '') if params else ''
        prompt_text = params.get('ref_text', '') if params else ''
        
        # 增加参数验证
        if not prompt_text or not prompt_text.strip():
            logger.warning("参考文本为空，使用默认值")
            prompt_text = "这是一段用于参考的文本，请使用这段文本的风格和语气。"
        
        # 清晰记录合成参数，使用明确的分隔确保日志不会连在一起
        logger.info("----- GPT-SOVITS 合成请求开始 -----")
        logger.info(f"要合成的文本: '{text}'")
        logger.info(f"参考文本: '{prompt_text}'")
        logger.info(f"参考音频: '{ref_audio_path}'")
        
        # 验证参考音频路径
        if not ref_audio_path:
            logger.error("参考音频路径为空，无法生成音频")
            return None
        
        if not os.path.exists(ref_audio_path):
            logger.error(f"参考音频文件不存在: {ref_audio_path}")
            return None
        
        # 分析角色和参考音频路径
        ref_audio_filename = os.path.basename(ref_audio_path)
        character_dir = os.path.dirname(ref_audio_path)
        character_name = os.path.basename(character_dir)
        
        # 确保实际文本和参考文本不同
        if prompt_text == text:
            logger.warning("警告: 参考文本与要合成的文本相同，这可能导致错误的合成结果")
            # 添加一个标记以区分 
            prompt_text = f"{prompt_text} (参考用)"
        
        logger.info(f"使用角色: {character_name}, 参考音频: {ref_audio_filename}")
        
        # 明确区分要合成的文本和参考文本
        text_to_synthesize = text  # 这是实际要合成的文本
        reference_prompt = prompt_text  # 这是用于参考的文本
        
        # 严格按照api_v2.md文档构造请求负载
        # 直接发送完整的参考音频路径给API
        # 假设API服务器能够访问此路径
        api_ref_audio_path = ref_audio_path
        
        # 确保完全遵循API要求，不添加任何额外字段
        payload = {
            "text": text_to_synthesize,         # 要合成的文本（必需）
            "text_lang": "zh",                  # 文本语言（必需）
            "ref_audio_path": api_ref_audio_path, # 参考音频路径（必需），发送绝对路径
            "prompt_text": reference_prompt,    # 参考文本（可选）
            "prompt_lang": "zh",                # 参考文本语言（必需）
            "top_k": 5,                         # top k采样
            "top_p": 1.0,                       # top p采样
            "temperature": 1.0,                 # 采样温度
            "text_split_method": "cut0",        # 文本分割方法
            "batch_size": 8,                    # 推理批大小
            "batch_threshold": 0.75,            # 批分割阈值
            "split_bucket": True,               # 是否将批分割为多个桶
            "speed_factor": 1.0,                # 控制合成音频的速度
            "media_type": "wav",                # 输出音频格式，修改为wav
            "streaming_mode": False,            # 是否返回流式响应，修改为False
            "parallel_infer": True,             # 是否使用并行推理
            "repetition_penalty": 1.35          # T2S模型的重复惩罚
        }
        
        # 覆盖默认参数，但不覆盖关键的文本参数
        if params:
            for key, value in params.items():
                if key in payload and key not in ["text", "prompt_text", "ref_audio_path"]:  # 不允许覆盖关键文本参数，包括ref_audio_path
                    payload[key] = value
        
        # 再次记录最终请求参数，确保text字段包含要合成的文本
        logger.info(f"API请求参数检查 - text: '{payload['text']}'")
        logger.info(f"API请求参数检查 - prompt_text: '{payload['prompt_text']}'")
        logger.info(f"API请求参数检查 - ref_audio_path (sent to API): '{payload['ref_audio_path']}'") # 添加日志打印发送给API的ref_audio_path
        
        try:
            # 使用API v2文档中的正确端点
            api_url = f"{self.api_base_url}/tts"
            
            # 添加详细的请求日志
            logger.debug(f"Sending API request:")
            logger.debug(f"  URL: {api_url}")
            logger.debug(f"  Method: POST")
            logger.debug(f"  Payload: {json.dumps(payload, ensure_ascii=False, indent=2)}") # 使用json.dumps美化输出
            
            response = requests.post(
                api_url,
                json=payload,
                timeout=self.timeout
            )
            
            # 检查响应
            if response.status_code < 400 and response.content:
                logger.info(f"GPT-SOVITS API成功返回音频数据，大小: {len(response.content)} 字节")
                return response.content
            else:
                logger.error(f"API调用失败，状态码: {response.status_code}")
                
                # 尝试提取错误消息
                try:
                    error_msg = response.json().get("message", "未知错误")
                    logger.error(f"API错误: {error_msg}")
                except:
                    pass
                    
                return None
                
        except requests.exceptions.Timeout:
            logger.error(f"GPT-SOVITS API请求超时 (超过 {self.timeout}秒)")
            return None
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"GPT-SOVITS API HTTP错误: {e}", exc_info=True)
            return None
            
        except requests.exceptions.RequestException as e:
            logger.error(f"GPT-SOVITS API请求异常: {e}", exc_info=True)
            return None
            
        except Exception as e:
            logger.error(f"调用GPT-SOVITS API时发生未知错误: {e}", exc_info=True)
            return None
    
    def stop_worker(self):
        """停止工作线程"""
        if self.worker_thread and self.worker_thread.is_alive():
            logger.info("正在停止TTS请求处理线程...")
            # 发送停止信号
            self.request_queue.put((None, None, None, None))
            # 等待线程结束
            self.worker_thread.join(timeout=5.0)
            logger.info("TTS请求处理线程已停止")
    
    def test_connection(self) -> Tuple[bool, str]:
        """测试与API服务器的连接
        
        Returns:
            Tuple[bool, str]: (成功标志, 消息)
        """
        # 定义可能的API测试端点列表
        test_paths = [
            "/",            # 根路径
            "/api",         # 常见API路径
            "/api/tts",     # 可能的TTS API路径
            "/tts",         # 直接的TTS端点
            "/v1",          # 版本化API路径
            "/v1/tts"       # 版本化TTS端点
        ]
        
        success = False
        last_error = ""
        
        # 尝试所有可能的路径
        for path in test_paths:
            try:
                api_url = f"{self.api_base_url}{path}"
                logger.info(f"尝试连接到: {api_url}")
                
                # 尝试发送GET请求
                response = requests.get(api_url, timeout=5)
                
                # 判断响应是否表示服务在运行
                if response.status_code == 200:
                    logger.info(f"连接成功: {api_url}, 状态码: {response.status_code}")
                    return True, f"服务器连接成功: {api_url}"
                elif response.status_code < 500:  # 4xx 错误意味着服务器在运行，但是路径可能不正确
                    logger.info(f"服务器运行中，但API路径可能不正确: {api_url}, 状态码: {response.status_code}")
                    
                    # 尝试检查tts端点是否可用
                    try:
                        tts_url = f"{self.api_base_url}/tts"
                        logger.info(f"尝试连接到TTS专用端点: {tts_url}")
                        # 使用OPTIONS或HEAD请求检查端点是否可用
                        tts_response = requests.head(tts_url, timeout=3)
                        
                        if tts_response.status_code < 500:
                            # 再尝试使用POST请求，看是否接受请求体
                            test_payload = {"text": "测试"}
                            tts_test = requests.post(tts_url, json=test_payload, timeout=3)
                            
                            if tts_test.status_code < 500:
                                logger.info(f"TTS端点测试成功: {tts_url}")
                                return True, f"TTS端点测试成功: {tts_url}"
                    except Exception as e:
                        logger.warning(f"TTS端点测试失败: {str(e)}")
                    
                    # 只有服务器连接确认，但API路径可能不正确
                    return False, f"服务器已连接，但API路径可能不正确。请检查config.ini中的api_base_url设置，当前URL: {self.api_base_url}"
                
                last_error = f"服务器返回错误状态码: {response.status_code} (URL: {api_url})"
                
            except requests.exceptions.Timeout:
                last_error = f"连接超时: {api_url}"
                continue
                
            except requests.exceptions.ConnectionError:
                last_error = f"无法连接到服务器: {api_url}"
                continue
                
            except Exception as e:
                last_error = f"测试连接时发生错误: {str(e)} (URL: {api_url})"
                continue
        
        # 如果所有尝试都失败
        logger.error(f"所有连接尝试均失败，最后错误: {last_error}")
        return False, f"TTS服务连接失败: {last_error}"
    
    def list_characters(self) -> List[Dict[str, Any]]:
        """获取可用角色列表
        
        Returns:
            List[Dict[str, Any]]: 角色信息列表
        """
        character_list = []
        
        try:
            # 检查角色根目录是否存在
            if not self.character_base_dir or not os.path.exists(self.character_base_dir):
                logger.warning(f"角色根目录不存在或未配置: {self.character_base_dir}")
                return character_list
                
            # 遍历角色根目录
            for item in os.listdir(self.character_base_dir):
                char_dir = os.path.join(self.character_base_dir, item)
                
                if os.path.isdir(char_dir):
                    # 查找参考音频文件
                    ref_audio_files = [f for f in os.listdir(char_dir) if f.endswith(('.wav', '.mp3'))]
                    
                    # 查找参考文本文件
                    ref_text_files = [f for f in os.listdir(char_dir) if f.endswith('.txt')]
                    
                    if ref_audio_files:
                        # 读取参考文本
                        ref_text = ""
                        if ref_text_files:
                            ref_text_path = os.path.join(char_dir, ref_text_files[0])
                            try:
                                with open(ref_text_path, 'r', encoding='utf-8') as f:
                                    ref_text = f.read().strip()
                            except Exception as e:
                                logger.warning(f"读取参考文本文件失败: {ref_text_path}, 错误: {e}")
                        
                        # 添加角色信息
                        character_list.append({
                            "name": item,
                            "ref_audio_path": os.path.join(char_dir, ref_audio_files[0]),
                            "ref_text": ref_text
                        })
            
            logger.info(f"找到 {len(character_list)} 个可用角色")
            return character_list
            
        except Exception as e:
            logger.error(f"获取角色列表时发生错误: {e}", exc_info=True)
            return character_list

    def __del__(self):
        """析构函数，确保工作线程正确停止"""
        self.stop_worker()

if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.DEBUG)
    
    client = GPTSoVITSClient()
    
    # 测试连接
    success, message = client.test_connection()
    print(f"连接测试: {message}")
    
    if success:
        # 获取角色列表
        characters = client.list_characters()
        print(f"可用角色: {len(characters)}")
        
        if characters:
            # 测试生成音频
            char = characters[0]
            print(f"使用角色: {char['name']}")
            
            # 使用队列模式测试
            def audio_callback(audio_data, error):
                if audio_data:
                    output_path = "test_output_queue.wav"
                    with open(output_path, "wb") as f:
                        f.write(audio_data)
                    print(f"队列模式测试音频已保存到: {output_path}")
                else:
                    print(f"队列模式生成音频失败: {error}")
            
            # 添加到队列
            client.queue_audio_request(
                "这是一个测试文本，用于验证GPT-SOVITS客户端队列模式是否正常工作。",
                {
                    "ref_audio_path": char["ref_audio_path"],
                    "ref_text": char["ref_text"]
                },
                audio_callback
            )
            
            # 等待队列处理完成
            import time
            time.sleep(10)
            
            # 停止工作线程
            client.stop_worker()
