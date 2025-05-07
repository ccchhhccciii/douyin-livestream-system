"""
话术生成提示词模板模块。
定义用于生成产品话术的提示词模板。
"""

class ScriptGeneratorPrompt:
    # 基础提示词，指导AI生成销售话术
    BASE_PROMPT = """你是一位专业的直播话术编写专家，请根据产品信息设计抖音直播高转化率话术脚本，包含以下要素：
    1. 抓人眼球的开场白
    2. 二到三个核心卖点
    3. 性价比对比
    4. 痛点解决方案
    5. 优惠说明
    6. 限时提醒
    7. 一到二个消除疑虑话术
    8. 二到三个互动问题
    
    要求：
    - 脚本控制在三百到四百字
    - 使用高度口语化生动亲切的表达
    - 将所有数字、时间、符号转为自然中文
    - 移除装饰性标点、标题、头尾注释
    - 语言自然流畅，有感染力
    - 避免过度夸张和虚假宣传
    
    请直接输出话术内容，不要包含解释或其他无关内容。
    """
    
    # 产品信息提示词部分
    PRODUCT_PROMPT = """
    产品信息:
    {product_info}
    """
    
    @staticmethod
    def get_complete_prompt(product_info):
        """生成完整的提示词，结合基础提示词和产品信息。
        
        Args:
            product_info (str): 产品基本信息
            
        Returns:
            str: 完整的提示词
        """
        return ScriptGeneratorPrompt.BASE_PROMPT + ScriptGeneratorPrompt.PRODUCT_PROMPT.format(product_info=product_info)
