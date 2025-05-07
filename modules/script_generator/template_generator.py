"""
话术变体模板生成引擎模块。
提供与LLM交互的功能，根据基础话术生成话术变体模板。
"""

import os
import json
import logging
import datetime
from typing import List, Optional, Dict, Any, Union

from modules.script_generator.template_generator_prompt import TemplateGeneratorPrompt

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TemplateGenerator:
    """话术变体模板生成引擎，支持使用不同LLM模型基于现有话术生成变体模板。"""
    
    def __init__(self, ollama_client=None, volcengine_client=None, base_dir="data"):
        """初始化话术变体模板生成器。
        
        Args:
            ollama_client: Ollama LLM客户端实例
            volcengine_client: 火山引擎LLM客户端实例
            base_dir (str): 数据存储的基础目录
        """
        self.ollama_client = ollama_client
        self.volcengine_client = volcengine_client
        self.base_dir = base_dir
        self.generation_prompt_template = TemplateGeneratorPrompt.get_complete_prompt
    
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
    
    def generate_template(self, script_content: str, model_id: str, count: int = 1) -> List[str]:
        """同步生成指定数量的话术变体模板。
        
        Args:
            script_content (str): 基础话术内容
            model_id (str): 模型ID
            count (int): 生成模板的数量，默认为1
            
        Returns:
            List[str]: 生成的变体模板列表
        """
        client, is_ollama = self._get_client_for_model(model_id)
        if not client:
            logger.error(f"无法为模型 {model_id} 找到适用的客户端")
            return []
        
        prompt = self.generation_prompt_template(script_content)
        results = []
        
        logger.info(f"开始生成 {count} 份话术变体模板，使用模型 {model_id}")
        
        for i in range(count):
            try:
                logger.info(f"正在生成第 {i+1}/{count} 份变体模板")
                
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
                    logger.info(f"成功生成第 {i+1} 份变体模板，长度：{len(response)}")
                else:
                    logger.warning(f"第 {i+1} 份变体模板生成失败，返回为空")
            
            except Exception as e:
                logger.exception(f"生成第 {i+1} 份变体模板时出错: {e}")
        
        logger.info(f"变体模板生成完成，成功：{len(results)}/{count}")
        return results
    
    def generate_template_stream(self, script_content: str, model_id: str):
        """流式生成话术变体模板，适合UI实时显示。
        
        Args:
            script_content (str): 基础话术内容
            model_id (str): 模型ID
            
        Yields:
            str: 生成的变体模板片段
        """
        client, is_ollama = self._get_client_for_model(model_id)
        if not client:
            logger.error(f"无法为模型 {model_id} 找到适用的客户端")
            yield None
            return
        
        prompt = self.generation_prompt_template(script_content)
        
        try:
            logger.info(f"开始流式生成变体模板，使用模型 {model_id}")
            
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
            
            logger.info("流式生成变体模板完成")
            
        except Exception as e:
            logger.exception(f"流式生成变体模板时出错: {e}")
            yield None
    
    def save_template(self, product_id: str, template_content: str) -> str:
        """保存生成的变体模板到指定产品目录的templates文件夹。
        
        Args:
            product_id (str): 产品ID
            template_content (str): 变体模板内容
            
        Returns:
            str: 保存的文件路径
        """
        # 构建目录路径
        product_dir = os.path.join(self.base_dir, "products", product_id)
        template_dir = os.path.join(product_dir, "templates")
        
        # 确保目录存在
        os.makedirs(template_dir, exist_ok=True)
        
        # 生成文件名
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        # 扫描现有文件确定序号
        existing_files = []
        if os.path.exists(template_dir):
            existing_files = [f for f in os.listdir(template_dir) if f.endswith(".txt")]
        
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
        file_path = os.path.join(template_dir, file_name)
        
        # 写入文件
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(template_content)
            logger.info(f"变体模板已保存到: {file_path}")
            return file_path
        except Exception as e:
            logger.exception(f"保存变体模板时出错: {e}")
            raise
    
    def get_script_content(self, product_id: str, script_id: str) -> Optional[str]:
        """获取指定产品和脚本ID的话术内容。
        
        Args:
            product_id (str): 产品ID
            script_id (str): 脚本ID（文件名，如 "001.txt"）
            
        Returns:
            Optional[str]: 话术内容，如果不存在则返回None
        """
        script_path = os.path.join(self.base_dir, "products", product_id, "script", script_id)
        
        if not os.path.exists(script_path):
            logger.warning(f"话术文件不存在: {script_path}")
            return None
        
        try:
            with open(script_path, "r", encoding="utf-8") as f:
                content = f.read()
            logger.info(f"成功读取话术内容: {script_path}")
            return content
        except Exception as e:
            logger.exception(f"读取话术内容时出错: {e}")
            return None
    
    def get_all_scripts(self, product_id: str) -> Dict[str, str]:
        """获取指定产品的所有话术文件。
        
        Args:
            product_id (str): 产品ID
            
        Returns:
            Dict[str, str]: 话术ID到文件路径的映射
        """
        script_dir = os.path.join(self.base_dir, "products", product_id, "script")
        
        if not os.path.exists(script_dir):
            logger.warning(f"话术目录不存在: {script_dir}")
            return {}
        
        result = {}
        try:
            for file_name in os.listdir(script_dir):
                if file_name.endswith(".txt"):
                    script_id = file_name
                    file_path = os.path.join(script_dir, file_name)
                    result[script_id] = file_path
            
            logger.info(f"产品 {product_id} 共有 {len(result)} 个话术文件")
            return result
        except Exception as e:
            logger.exception(f"获取话术文件列表时出错: {e}")
            return {}
