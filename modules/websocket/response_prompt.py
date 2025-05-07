"""
response_prompt模块，负责加载和处理产品回复提示词。

主要功能包括：
1. 加载产品response_prompt.md文件
2. 根据用户问题类型选择合适的回复模板
3. 生成针对特定用户的回复内容
"""

import os
import re
import logging
import random
from typing import Dict, List, Optional, Tuple, Any

# 配置日志路径到data目录
log_dir = 'data/logs'

class ResponsePromptHandler:
    """处理产品回复提示词的类"""
    
    # 问题类型的关键词映射
    QUESTION_TYPE_KEYWORDS = {
        'price': ['价格', '多少钱', '贵', '便宜', '优惠', '打折', '促销', '活动价'],
        'material': ['材质', '面料', '舒适', '透气', '闷热', '质量', '手感', '触感'],
        'effect': ['效果', '防晒', '防护', '紫外线', 'uv', 'UPF', '晒黑', '晒伤'],
        'usage': ['清洗', '水洗', '寿命', '用多久', '洗几次', '耐用', '清洁', '保养'],
        'shipping': ['发货', '物流', '快递', '到货', '收货', '几天', '邮费', '包邮'],
        'service': ['退款', '退货', '换货', '售后', '保障', '质保', '联系', '客服']
    }
    
    def __init__(self, product_id: str = None):
        """
        初始化回复提示词处理器
        
        Args:
            product_id: 产品ID（目录名称），如果为None则不加载任何产品
        """
        self.logger = logging.getLogger(__name__)
        self.product_id = None
        self.prompt_content = {}
        self.response_templates = {}
        
        if product_id:
            self.load_product(product_id)
    
    def load_product(self, product_id: str) -> bool:
        """
        加载指定产品的回复提示词
        
        Args:
            product_id: 产品ID（目录名称）
            
        Returns:
            加载成功返回True，否则返回False
        """
        self.product_id = product_id
        prompt_path = f'data/products/{product_id}/response_prompt.md'
        
        try:
            if not os.path.exists(prompt_path):
                self.logger.error(f"回复提示词文件不存在: {prompt_path}")
                return False
                
            with open(prompt_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            self.prompt_content = self._parse_prompt_content(content)
            self.response_templates = self._extract_response_templates(self.prompt_content)
            
            self.logger.info(f"成功加载产品回复提示词: {product_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"加载产品回复提示词失败: {e}")
            return False
    
    def _parse_prompt_content(self, content: str) -> Dict[str, Any]:
        """
        解析提示词内容
        
        Args:
            content: 原始markdown提示词内容
            
        Returns:
            解析后的提示词内容字典
        """
        result = {
            'product_name': '',
            'core_points': [],
            'parameters': {},
            'question_templates': {},
            'interaction_guides': []
        }
        
        # 提取产品名称
        product_match = re.search(r'## 产品：(.*?)$', content, re.MULTILINE)
        if product_match:
            result['product_name'] = product_match.group(1).strip()
        
        # 提取核心卖点
        core_points_section = self._extract_section(content, '### 产品核心卖点', '###')
        if core_points_section:
            # 匹配有序列表项: 1. 内容
            points = re.findall(r'\d+\.\s+(.*?)$', core_points_section, re.MULTILINE)
            result['core_points'] = [p.strip() for p in points]
        
        # 提取产品参数
        params_section = self._extract_section(content, '### 产品关键参数', '###')
        if params_section:
            # 匹配无序列表项: - 参数: 值
            params = re.findall(r'-\s+(.*?)：(.*?)$', params_section, re.MULTILINE)
            result['parameters'] = {k.strip(): v.strip() for k, v in params}
        
        # 提取问题模板
        # 首先提取整个"常见问题回复指南"部分
        qa_section = self._extract_section(content, '### 常见问题回复指南', '###')
        if qa_section:
            # 然后提取每个子问题类型
            question_types = re.findall(r'#### (.*?)问题\s+\*\*问题示例\*\*：(.*?)\s+\*\*回复模板\*\*：\s+"(.*?)"', 
                                        qa_section, re.DOTALL)
            
            for q_type, examples, template in question_types:
                q_type = q_type.strip()
                examples = [e.strip() for e in examples.split('？') if e.strip()]
                template = template.strip()
                
                result['question_templates'][q_type] = {
                    'examples': examples,
                    'template': template
                }
        
        # 提取互动引导话术
        guides_section = self._extract_section(content, '### 互动引导话术', '')
        if guides_section:
            # 匹配有序列表项: 1. "话术内容"
            guides = re.findall(r'\d+\.\s+"(.*?)"', guides_section, re.MULTILINE)
            result['interaction_guides'] = [g.strip() for g in guides]
        
        return result
    
    def _extract_section(self, content: str, section_start: str, section_end: str) -> str:
        """
        从内容中提取特定部分
        
        Args:
            content: 原始内容
            section_start: 部分开始标记
            section_end: 部分结束标记，如果为空则提取到文件末尾
            
        Returns:
            提取的部分内容，如果未找到则返回空字符串
        """
        start_idx = content.find(section_start)
        if start_idx == -1:
            return ''
            
        start_idx += len(section_start)
        
        if section_end:
            end_idx = content.find(section_end, start_idx)
            if end_idx == -1:
                end_idx = len(content)
        else:
            end_idx = len(content)
            
        return content[start_idx:end_idx].strip()
    
    def _extract_response_templates(self, parsed_content: Dict[str, Any]) -> Dict[str, str]:
        """
        从解析内容中提取回复模板
        
        Args:
            parsed_content: 解析后的提示词内容
            
        Returns:
            回复模板字典，键为问题类型，值为回复模板
        """
        templates = {}
        
        # 提取每个问题类型的回复模板
        for q_type, data in parsed_content.get('question_templates', {}).items():
            template = data.get('template', '')
            if template:
                key = q_type.lower().split('相关')[0]  # 如'价格相关'变成'价格'
                templates[key] = template
        
        return templates
    
    def get_response_template(self, question_type: str) -> Optional[str]:
        """
        获取指定问题类型的回复模板
        
        Args:
            question_type: 问题类型
            
        Returns:
            回复模板，如果未找到则返回None
        """
        return self.response_templates.get(question_type)
    
    def get_random_interaction_guide(self) -> str:
        """
        获取随机互动引导话术
        
        Returns:
            随机互动引导话术，如果不存在则返回空字符串
        """
        guides = self.prompt_content.get('interaction_guides', [])
        return random.choice(guides) if guides else ""
    
    def _detect_question_type(self, question: str) -> str:
        """
        检测问题类型
        
        Args:
            question: 用户问题
            
        Returns:
            问题类型，如果未匹配到则返回'general'
        """
        # 按关键词匹配问题类型
        for q_type, keywords in self.QUESTION_TYPE_KEYWORDS.items():
            for keyword in keywords:
                if keyword in question:
                    return q_type
        
        # 未匹配到关键词，返回通用类型
        return 'general'
    
    def _map_question_type_to_template_key(self, detected_type: str) -> str:
        """
        将检测到的问题类型映射到模板键
        
        Args:
            detected_type: 检测到的问题类型
            
        Returns:
            映射后的模板键
        """
        # 映射关系
        mapping = {
            'price': '价格',
            'material': '材质和舒适度',
            'effect': '防晒效果',
            'usage': '使用寿命和清洗',
            'shipping': '物流和售后',
            'service': '物流和售后'
        }
        
        return mapping.get(detected_type, '价格')  # 默认返回价格模板
    
    def generate_response(self, question: str, nickname: str) -> str:
        """
        根据用户问题生成回复
        
        Args:
            question: 用户问题
            nickname: 用户昵称
            
        Returns:
            生成的回复内容
        """
        if not self.response_templates:
            return f"{nickname}，谢谢您的问题，请稍等，我们的客服会尽快为您解答。"
            
        # 检测问题类型
        detected_type = self._detect_question_type(question)
        
        # 映射到模板键
        template_key = self._map_question_type_to_template_key(detected_type)
        
        # 获取回复模板
        template = self.get_response_template(template_key)
        
        # 如果未找到对应模板，使用通用模板
        if not template:
            product_name = self.prompt_content.get('product_name', '我们的产品')
            return f"{nickname}，感谢您对{product_name}的关注！您的问题我们已经记录，稍后会详细回复您。"
        
        # 填充模板
        response = template.format(用户昵称=nickname)
        
        return response
    
    def get_product_info(self) -> Dict[str, Any]:
        """
        获取产品信息
        
        Returns:
            产品信息字典
        """
        result = {
            'name': self.prompt_content.get('product_name', ''),
            'core_points': self.prompt_content.get('core_points', []),
            'parameters': self.prompt_content.get('parameters', {})
        }
        
        # 转换部分参数为更友好的格式
        params = result['parameters']
        if '价格' in params:
            try:
                price_str = params['价格'].split('，')[0]
                price_value = float(re.search(r'([\d.]+)', price_str).group(1))
                result['price'] = price_value
            except:
                result['price'] = 0
        
        if '材质' in params:
            result['material'] = params['材质']
        
        return result


# 使用示例
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 创建处理器
    handler = ResponsePromptHandler('女性防晒面罩')
    
    # 测试问题
    test_questions = [
        "这个防晒面罩要多少钱？",
        "面罩会不会很闷热啊？",
        "防晒效果真的好吗？",
        "可以清洗吗？能用多久？",
        "你们多久能发货？"
    ]
    
    # 测试回复
    for q in test_questions:
        response = handler.generate_response(q, "测试用户")
        print(f"问题: {q}")
        print(f"回复: {response}\n")
    
    # 测试随机互动引导
    print(f"随机互动引导: {handler.get_random_interaction_guide()}")
