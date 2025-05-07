"""
话术变体模板提示词模块。
定义用于生成话术变体模板的提示词。
"""

class TemplateGeneratorPrompt:
    # 基础提示词，指导AI生成话术变体模板
    BASE_PROMPT = """你是一位专业的直播话术编写专家，请根据产品基础话术制作抖音直播话术变体模板。

    变体模板要求：
    1. 使用"{选项1|选项2|选项3}"格式标记可替换的内容
    2. 每个替换组内提供2-4个语义相近但表达不同的选项
    3. 替换组应涵盖重要名词、形容词、动词和短语
    4. 保持原始话术的销售重点和卖点不变
    5. 确保所有变体组合在语法和语义上通顺
    6. 替换选项应符合直播口语化表达风格
    
    示例：
    基础话术: 咱家这款蚊香是某植某物的檀香型蚊香,不冒黑烟不呛鼻子,驱蚊效果要比普通的老式蚊香强个三到五倍,包括它用途比较广泛,室外都能去用。
    
    变体模板: {咱家这款|我们这款}蚊香是{某植某物|特定品牌的}檀香型蚊香,{不冒黑烟|不会产生浓烟},{不呛鼻子|不会刺激呼吸道},{驱蚊效果|防蚊能力}要比{普通的老式蚊香|传统蚊香}强个三到五倍,{包括它用途比较广泛|而且适用范围广泛},{室外都能去用|户外也可以使用}。
    
    请直接输出变体模板内容，不要包含解释或其他无关内容。
    """
    
    # 产品话术提示词部分
    SCRIPT_PROMPT = """
    产品基础话术:
    {script_content}
    """
    
    @staticmethod
    def get_complete_prompt(script_content):
        """生成完整的提示词，结合基础提示词和产品话术。
        
        Args:
            script_content (str): 产品基础话术内容
            
        Returns:
            str: 完整的提示词
        """
        return TemplateGeneratorPrompt.BASE_PROMPT + TemplateGeneratorPrompt.SCRIPT_PROMPT.format(script_content=script_content)
