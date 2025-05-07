"""
话术变体模板解析引擎模块。
提供解析"{选项1|选项2}"格式变体模板的功能，支持嵌套变体和多种选择策略。
"""

import re
import random
import time
import logging
import os
from typing import List, Dict, Tuple, Optional, Callable, Any, Union

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class VariantNode:
    """变体节点，用于构建变体模板的语法树结构。"""
    
    def __init__(self, text: str = "", is_variant: bool = False):
        """初始化变体节点。
        
        Args:
            text (str): 节点文本内容
            is_variant (bool): 是否为变体组节点
        """
        self.text = text          # 纯文本或选项组文本
        self.is_variant = is_variant  # 是否为变体选项组
        self.children = []        # 子节点，用于嵌套变体
        self.options = []         # 变体选项列表
        self.last_selected = {}   # 上次选择记录 {strategy: (option_index, timestamp)}
    
    def add_child(self, child: 'VariantNode'):
        """添加子节点。
        
        Args:
            child (VariantNode): 子节点
        """
        self.children.append(child)
    
    def set_options(self, options: List[str]):
        """设置变体选项列表。
        
        Args:
            options (List[str]): 变体选项列表
        """
        self.options = options
        
    def __str__(self):
        """字符串表示。"""
        if self.is_variant:
            return f"[VARIANT: {', '.join(self.options)}]"
        else:
            return f"[TEXT: {self.text}]"

class TemplateParser:
    """话术变体模板解析引擎，支持解析"{选项1|选项2}"格式的变体标记和多种选择策略。"""
    
    # 变体标记正则表达式，用于匹配{选项1|选项2}格式
    VARIANT_PATTERN = re.compile(r'{([^{}]*(?:{[^{}]*}[^{}]*)*)}')
    
    # 选项分隔符正则表达式，用于分割|符号，但忽略嵌套括号内的|
    OPTION_SEPARATOR = re.compile(r'\|(?![^{]*})')
    
    # 选择策略
    STRATEGY_RANDOM = "random"    # 随机选择
    STRATEGY_WEIGHTED = "weighted"  # 权重选择
    STRATEGY_ROTATION = "rotation"  # 轮换选择
    
    def __init__(self, memory_time: int = 3600):
        """初始化模板解析器。
        
        Args:
            memory_time (int): 变体选择记忆时间（秒），默认1小时
        """
        self.memory_time = memory_time  # 记忆时间，单位秒
        self.rotation_indexes = {}      # 轮换策略的当前索引跟踪
    
    def parse_template(self, template: str) -> VariantNode:
        """解析变体模板，构建语法树。
        
        Args:
            template (str): 变体模板文本
            
        Returns:
            VariantNode: 模板根节点
        """
        # 创建根节点
        root = VariantNode()
        
        # 从位置0开始解析
        self._parse_node(template, 0, root)
        
        return root
    
    def _parse_node(self, template: str, start_pos: int, parent: VariantNode) -> int:
        """递归解析模板节点。
        
        Args:
            template (str): 完整模板文本
            start_pos (int): 当前解析位置
            parent (VariantNode): 父节点
            
        Returns:
            int: 解析结束位置
        """
        pos = start_pos
        text_start = pos
        
        while pos < len(template):
            # 查找变体标记开始位置
            if template[pos] == '{':
                # 处理文本节点
                if pos > text_start:
                    text_node = VariantNode(template[text_start:pos], False)
                    parent.add_child(text_node)
                
                # 找到匹配的结束括号
                bracket_count = 1
                option_start = pos + 1
                
                i = pos + 1
                while i < len(template) and bracket_count > 0:
                    if template[i] == '{':
                        bracket_count += 1
                    elif template[i] == '}':
                        bracket_count -= 1
                    i += 1
                
                if bracket_count == 0:
                    # 提取变体选项内容
                    variant_content = template[option_start:i-1]
                    
                    # 创建变体节点
                    variant_node = VariantNode(is_variant=True)
                    
                    # 分割变体选项，处理嵌套情况
                    options = self._split_options(variant_content)
                    variant_node.set_options(options)
                    
                    # 递归解析选项中的嵌套变体
                    for option in options:
                        option_node = VariantNode()
                        self._parse_node(option, 0, option_node)
                        variant_node.add_child(option_node)
                    
                    parent.add_child(variant_node)
                    
                    # 更新位置
                    pos = i
                    text_start = pos
                else:
                    # 未找到匹配的结束括号，视为普通文本
                    pos += 1
            else:
                pos += 1
        
        # 处理剩余文本
        if pos > text_start:
            text_node = VariantNode(template[text_start:pos], False)
            parent.add_child(text_node)
        
        return pos
    
    def _split_options(self, variant_content: str) -> List[str]:
        """分割变体选项，处理嵌套括号的情况。
        
        Args:
            variant_content (str): 变体内容，如"选项1|选项2{子选项1|子选项2}|选项3"
            
        Returns:
            List[str]: 分割后的选项列表
        """
        # 使用正则表达式分割，忽略嵌套括号内的|符号
        options = []
        last_end = 0
        bracket_count = 0
        
        for i, char in enumerate(variant_content):
            if char == '{':
                bracket_count += 1
            elif char == '}':
                bracket_count -= 1
            elif char == '|' and bracket_count == 0:
                options.append(variant_content[last_end:i])
                last_end = i + 1
        
        # 添加最后一个选项
        if last_end < len(variant_content):
            options.append(variant_content[last_end:])
        
        return options
    
    def render_template(self, template: str, strategy: str = STRATEGY_RANDOM, 
                       weights: Dict[str, float] = None) -> str:
        """渲染变体模板，生成最终话术。
        
        Args:
            template (str): 变体模板文本
            strategy (str): 选择策略，可选值: "random", "weighted", "rotation"
            weights (Dict[str, float], optional): 变体选项权重配置
            
        Returns:
            str: 渲染后的话术
        """
        logger.info(f"开始渲染模板，使用策略：{strategy}")
        
        # 解析模板
        try:
            root = self.parse_template(template)
            
            # 渲染模板
            result = self._render_node(root, strategy, weights)
            
            logger.info(f"模板渲染完成，长度：{len(result)}")
            return result
        
        except Exception as e:
            logger.exception(f"渲染模板时出错: {e}")
            # 如果解析失败，返回原始模板内容
            return template
    
    def render_template_with_id(self, template_path: str, strategy: str = STRATEGY_RANDOM, 
                               weights: Dict[str, float] = None) -> str:
        """根据模板文件路径渲染模板。
        
        Args:
            template_path (str): 变体模板文件路径
            strategy (str): 选择策略
            weights (Dict[str, float], optional): 变体选项权重
            
        Returns:
            str: 渲染后的话术
        """
        if not os.path.exists(template_path):
            logger.error(f"模板文件不存在: {template_path}")
            return ""
        
        try:
            with open(template_path, "r", encoding="utf-8") as f:
                template_content = f.read()
            
            return self.render_template(template_content, strategy, weights)
        
        except Exception as e:
            logger.exception(f"读取或渲染模板文件时出错: {e}")
            return ""
    
    def _render_node(self, node: VariantNode, strategy: str, 
                    weights: Dict[str, float] = None) -> str:
        """递归渲染节点。
        
        Args:
            node (VariantNode): 要渲染的节点
            strategy (str): 选择策略
            weights (Dict[str, float], optional): 变体选项权重
            
        Returns:
            str: 渲染结果
        """
        if not node.is_variant:
            # 纯文本节点直接返回文本
            if not node.children:
                return node.text
            
            # 递归渲染子节点
            result = ""
            for child in node.children:
                result += self._render_node(child, strategy, weights)
            return result
        
        # 变体节点，根据策略选择选项
        selected_option_index = self._select_option(node, strategy, weights)
        
        if 0 <= selected_option_index < len(node.children):
            return self._render_node(node.children[selected_option_index], strategy, weights)
        
        # 如果没有子节点对应选中的选项，返回空字符串
        logger.warning(f"选中的选项索引 {selected_option_index} 没有对应的子节点")
        return ""
    
    def _select_option(self, node: VariantNode, strategy: str, 
                      weights: Dict[str, float] = None) -> int:
        """根据策略选择变体选项。
        
        Args:
            node (VariantNode): 变体节点
            strategy (str): 选择策略
            weights (Dict[str, float], optional): 变体选项权重
            
        Returns:
            int: 选中的选项索引
        """
        if not node.options:
            return -1
        
        # 检查是否需要避免重复选择
        current_time = time.time()
        if strategy in node.last_selected:
            last_index, last_time = node.last_selected[strategy]
            # 如果距离上次选择时间小于记忆时间，则避免选择相同选项
            if current_time - last_time < self.memory_time:
                if len(node.options) > 1:  # 只有当有多个选项时才避免重复
                    if strategy == self.STRATEGY_RANDOM:
                        available_indexes = [i for i in range(len(node.options)) if i != last_index]
                        selected_index = random.choice(available_indexes)
                        node.last_selected[strategy] = (selected_index, current_time)
                        return selected_index
        
        # 根据不同策略选择选项
        if strategy == self.STRATEGY_RANDOM:
            # 随机选择
            selected_index = random.randint(0, len(node.options) - 1)
        
        elif strategy == self.STRATEGY_WEIGHTED:
            # 权重选择
            if not weights:
                # 无权重配置时退化为随机选择
                selected_index = random.randint(0, len(node.options) - 1)
            else:
                # 构建权重列表
                option_weights = []
                for option in node.options:
                    # 尝试查找权重，默认为1.0
                    option_weight = weights.get(option, 1.0)
                    option_weights.append(option_weight)
                
                # 计算总权重
                total_weight = sum(option_weights)
                if total_weight <= 0:
                    # 所有权重都是0或负数，使用均匀权重
                    selected_index = random.randint(0, len(node.options) - 1)
                else:
                    # 按权重随机选择
                    rand_value = random.uniform(0, total_weight)
                    cumulative_weight = 0
                    selected_index = 0
                    
                    for i, weight in enumerate(option_weights):
                        cumulative_weight += weight
                        if rand_value <= cumulative_weight:
                            selected_index = i
                            break
        
        elif strategy == self.STRATEGY_ROTATION:
            # 轮换选择
            # 使用变体内容的哈希作为唯一标识
            variant_key = hash("".join(node.options))
            if variant_key not in self.rotation_indexes:
                self.rotation_indexes[variant_key] = 0
            
            # 获取当前索引并递增
            selected_index = self.rotation_indexes[variant_key]
            self.rotation_indexes[variant_key] = (selected_index + 1) % len(node.options)
        
        else:
            # 未知策略，使用随机选择
            logger.warning(f"未知的选择策略: {strategy}，使用随机选择")
            selected_index = random.randint(0, len(node.options) - 1)
        
        # 记录本次选择
        node.last_selected[strategy] = (selected_index, current_time)
        return selected_index
    
    def analyze_template(self, template: str) -> Dict[str, Any]:
        """分析变体模板的结构和统计信息。
        
        Args:
            template (str): 变体模板文本
            
        Returns:
            Dict[str, Any]: 模板分析结果
        """
        try:
            # 解析模板
            root = self.parse_template(template)
            
            # 收集统计信息
            variant_count = 0
            option_count = 0
            max_options = 0
            nested_count = 0
            
            def analyze_node(node, depth=0):
                nonlocal variant_count, option_count, max_options, nested_count
                
                if node.is_variant:
                    variant_count += 1
                    option_count += len(node.options)
                    max_options = max(max_options, len(node.options))
                    
                    # 检查嵌套变体
                    for child in node.children:
                        has_nested = False
                        def check_nested(n):
                            nonlocal has_nested
                            if n.is_variant:
                                has_nested = True
                            for c in n.children:
                                check_nested(c)
                        
                        check_nested(child)
                        if has_nested:
                            nested_count += 1
                
                for child in node.children:
                    analyze_node(child, depth + 1)
            
            analyze_node(root)
            
            # 计算潜在的变体组合数量
            potential_combinations = 1
            
            def count_combinations(node):
                nonlocal potential_combinations
                if node.is_variant:
                    potential_combinations *= len(node.options)
                for child in node.children:
                    count_combinations(child)
            
            count_combinations(root)
            
            return {
                "variant_count": variant_count,
                "option_count": option_count,
                "average_options": option_count / variant_count if variant_count > 0 else 0,
                "max_options": max_options,
                "nested_count": nested_count,
                "potential_combinations": potential_combinations
            }
        
        except Exception as e:
            logger.exception(f"分析模板时出错: {e}")
            return {
                "error": str(e),
                "variant_count": 0,
                "option_count": 0,
                "average_options": 0,
                "max_options": 0,
                "nested_count": 0,
                "potential_combinations": 0
            }
    
    def get_all_options(self, template: str) -> List[List[str]]:
        """获取模板中所有变体选项。
        
        Args:
            template (str): 变体模板文本
            
        Returns:
            List[List[str]]: 所有变体选项列表
        """
        options_list = []
        
        try:
            # 使用正则表达式查找所有变体标记
            matches = self.VARIANT_PATTERN.finditer(template)
            
            for match in matches:
                variant_content = match.group(1)
                options = self._split_options(variant_content)
                options_list.append(options)
            
            return options_list
        
        except Exception as e:
            logger.exception(f"获取所有选项时出错: {e}")
            return []
    
    def highlight_variants(self, template: str) -> str:
        """高亮显示变体标记，用于调试和可视化。
        
        Args:
            template (str): 变体模板文本
            
        Returns:
            str: 带有高亮标记的文本
        """
        try:
            # 使用颜色标记替换变体
            highlighted = template
            
            # 查找所有变体标记
            matches = list(self.VARIANT_PATTERN.finditer(template))
            
            # 从后向前替换，避免位置偏移
            for match in reversed(matches):
                start, end = match.span()
                variant_content = match.group(1)
                
                # 将变体内容按选项分割
                options = self._split_options(variant_content)
                
                # 构建高亮文本
                highlight_text = "[" + "|".join([f"<{opt}>" for opt in options]) + "]"
                
                # 替换原文本
                highlighted = highlighted[:start] + highlight_text + highlighted[end:]
            
            return highlighted
        
        except Exception as e:
            logger.exception(f"高亮变体时出错: {e}")
            return template
