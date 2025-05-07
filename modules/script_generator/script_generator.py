"""
话术生成引擎模块。
提供与LLM交互的功能，生成产品销售话术。
"""

import os
import json
import logging
import datetime
from typing import List, Optional, Callable, Dict, Any, Union

from modules.script_generator.script_generator_prompt import ScriptGeneratorPrompt

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ScriptGenerator:
    """话术生成引擎，支持使用不同LLM模型生成产品销售话术。"""
    
    def __init__(self, ollama_client=None, volcengine_client=None, base_dir="data"):
        """初始化话术生成器。
        
        Args:
            ollama_client: Ollama LLM客户端实例
            volcengine_client: 火山引擎LLM客户端实例
            base_dir (str): 数据存储的基础目录
        """
        self.ollama_client = ollama_client
        self.volcengine_client = volcengine_client
        self.base_dir = base_dir
        self.generation_prompt_template = ScriptGeneratorPrompt.get_complete_prompt
    
    def _get_client_for_model(self, model_id):
        """根据模型ID获取相应的客户端实例。
        
        Args:
            model_id (str): 模型ID，可能是Ollama或火山引擎的模型
            
        Returns:
            tuple: (客户端实例, 是否为Ollama模型)
        """
        # 简单启发式方法判断模型类型
        if model_id and (":" in model_id or model_id.startswith("ollama")):
            return self.ollama_client, True
        else:
            return self.volcengine_client, False
    
    def generate_script(self, product_info: str, model_id: str, count: int = 1) -> List[str]:
        """同步生成指定数量的产品话术。
        
        Args:
            product_info (str): 产品信息
            model_id (str): 模型ID
            count (int): 生成话术的数量，默认为1
            
        Returns:
            List[str]: 生成的话术列表
        """
        client, is_ollama = self._get_client_for_model(model_id)
        if not client:
            logger.error(f"无法为模型 {model_id} 找到适用的客户端")
            return []
        
        prompt = self.generation_prompt_template(product_info)
        results = []
        
        logger.info(f"开始生成 {count} 份话术，使用模型 {model_id}")
        
        for i in range(count):
            try:
                logger.info(f"正在生成第 {i+1}/{count} 份话术")
                
                if is_ollama:
                    response = client.generate_completion(prompt, model=model_id)
                else:
                    response = client.generate_completion(
                        model=model_id,
                        prompt=prompt,
                        system_prompt=""
                    )
                
                if response:
                    results.append(response)
                    logger.info(f"成功生成第 {i+1} 份话术，长度：{len(response)}")
                else:
                    logger.warning(f"第 {i+1} 份话术生成失败，返回为空")
            
            except Exception as e:
                logger.exception(f"生成第 {i+1} 份话术时出错: {e}")
        
        logger.info(f"话术生成完成，成功：{len(results)}/{count}")
        return results
    
    def generate_script_stream(self, product_info: str, model_id: str):
        """流式生成产品话术，适合UI实时显示。
        
        Args:
            product_info (str): 产品信息
            model_id (str): 模型ID
            
        Yields:
            str: 生成的话术片段
        """
        client, is_ollama = self._get_client_for_model(model_id)
        if not client:
            logger.error(f"无法为模型 {model_id} 找到适用的客户端")
            yield None
            return
        
        prompt = self.generation_prompt_template(product_info)
        
        try:
            logger.info(f"开始流式生成话术，使用模型 {model_id}")
            
            if is_ollama:
                if hasattr(client, 'generate_completion_stream'):
                    stream = client.generate_completion_stream(prompt, model=model_id)
                    for chunk in stream:
                        yield chunk
                else:
                    logger.error("Ollama客户端不支持流式生成")
                    yield None
                    return
            else:
                if hasattr(client, 'generate_completion_stream'):
                    stream = client.generate_completion_stream(
                        model=model_id,
                        prompt=prompt,
                        system_prompt=""
                    )
                    for chunk in stream:
                        yield chunk
                else:
                    logger.error("火山引擎客户端不支持流式生成")
                    yield None
                    return
            
            logger.info("流式生成话术完成")
            
        except Exception as e:
            logger.exception(f"流式生成话术时出错: {e}")
            yield None
    
    def save_script(self, product_id: str, script_content: str) -> str:
        """保存生成的话术到指定产品目录。
        
        Args:
            product_id (str): 产品ID
            script_content (str): 话术内容
            
        Returns:
            str: 保存的文件路径
        """
        # 构建目录路径
        product_dir = os.path.join(self.base_dir, "products", product_id)
        script_dir = os.path.join(product_dir, "script")
        
        # 确保目录存在
        os.makedirs(script_dir, exist_ok=True)
        
        # 生成文件名
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        # 扫描现有文件确定序号
        existing_files = []
        if os.path.exists(script_dir):
            existing_files = [f for f in os.listdir(script_dir) if f.endswith(".txt")]
        
        next_num = 1
        if existing_files:
            try:
                # 提取现有文件的序号
                nums = [int(f.split(".")[0]) for f in existing_files if f.split(".")[0].isdigit()]
                if nums:
                    next_num = max(nums) + 1
            except (ValueError, IndexError) as e:
                logger.warning(f"解析现有文件序号时出错: {e}，使用默认序号 {next_num}")
        
        # 格式化序号为3位数字
        file_name = f"{next_num:03d}.txt"
        file_path = os.path.join(script_dir, file_name)
        
        # 写入文件
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(script_content)
            logger.info(f"话术已保存到: {file_path}")
            return file_path
        except Exception as e:
            logger.exception(f"保存话术时出错: {e}")
            raise
    
    def save_product_info(self, product_id: str, product_info: str) -> str:
        """保存产品信息到product_info.json。
        
        Args:
            product_id (str): 产品ID
            product_info (str): 产品信息
            
        Returns:
            str: 保存的文件路径
        """
        # 构建目录路径
        product_dir = os.path.join(self.base_dir, "products", product_id)
        
        # 确保目录存在
        os.makedirs(product_dir, exist_ok=True)
        
        # 构建文件路径
        file_path = os.path.join(product_dir, "product_info.json")
        
        # 准备数据
        try:
            # 尝试解析为JSON
            data = json.loads(product_info)
        except json.JSONDecodeError:
            # 非JSON格式，使用字符串作为描述
            data = {"description": product_info}
        
        # 写入文件
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            logger.info(f"产品信息已保存到: {file_path}")
            return file_path
        except Exception as e:
            logger.exception(f"保存产品信息时出错: {e}")
            raise
