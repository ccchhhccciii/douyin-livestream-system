"""
消息解析模块 - 解析WebSocket接收到的原始消息
转换不同格式的消息为统一的内部格式
"""

import json
import logging
import re
import unicodedata
from datetime import datetime 
from typing import Dict, Any, Optional, List, Tuple, Union

# 定义黑名单关键词用于消息过滤
BLACKLIST_KEYWORDS = ["直播间人数", "左上角", "参与一下", "$来了"] 

# 配置日志路径到data目录
log_dir = 'data/logs'

class MessageParser:
    """消息解析器，解析直播服务器发送的消息"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化消息解析器
        
        Args:
            config: 配置字典，包含解析规则和选项
        """
        # 设置日志
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # 配置参数
        self.config = config or {}
        
        # 支持的消息类型
        self.supported_types = self.config.get("supported_types", ["comment", "gift", "enter", "like", "follow"])
        
        self.logger.info("消息解析器初始化完成")
    
    def parse_message(self, raw_message: str) -> Optional[Dict[str, Any]]:
        """解析原始消息
        
        Args:
            raw_message: 原始消息字符串
            
        Returns:
            解析后的消息字典，失败返回None
        """
        try:
            # 尝试解析JSON
            data = json.loads(raw_message)
            
            # 识别消息类型并处理
            message_type = self._determine_message_type(data)
            if not message_type:
                return None
                
            # 根据消息类型调用相应的处理方法
            if message_type == "comment":
                return self._parse_comment(data)
            elif message_type == "gift":
                return self._parse_gift(data)
            elif message_type == "enter":
                return self._parse_enter(data)
            elif message_type == "like":
                return self._parse_like(data)
            elif message_type == "follow":
                return self._parse_follow(data)
            else:
                return None
                
        except json.JSONDecodeError:
            self.logger.warning(f"无法解析非JSON消息: {raw_message[:100]}...")
            return None
        except Exception as e:
            self.logger.error(f"解析消息时出错: {e}", exc_info=True)
            return None
    
    def _determine_message_type(self, data: Dict[str, Any]) -> Optional[str]:
        """确定消息类型
        
        Args:
            data: 解析后的JSON数据
            
        Returns:
            消息类型，无法确定则返回None
        """
        # 直接从消息中获取类型字段
        if "type" in data and isinstance(data["type"], str):
            msg_type = data["type"].lower()
            if msg_type in self.supported_types:
                return msg_type
        
        # 根据消息结构猜测类型
        if "method" in data:
            method = data["method"].lower()
            if "comment" in method or "chat" in method:
                return "comment"
            elif "gift" in method:
                return "gift"
            elif "enter" in method or "join" in method:
                return "enter"
            elif "like" in method:
                return "like"
            elif "follow" in method:
                return "follow"
        
        # 检查消息内容特征
        if "data" in data and isinstance(data["data"], dict):
            content = data["data"]
            if "content" in content or "text" in content or "comment" in content:
                return "comment"
            elif "gift" in content or "gift_id" in content or "gift_name" in content:
                return "gift"
            elif "enter" in content or "join" in content:
                return "enter"
            
        # 无法确定类型
        return None
    
    def _parse_comment(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """解析评论消息
        
        Args:
            data: 原始消息数据
            
        Returns:
            统一格式的评论消息
        """
        # 提取用户信息
        user = self._extract_user_info(data)
        
        # 提取评论内容
        content = ""
        if "content" in data:
            content = data["content"]
        elif "data" in data and isinstance(data["data"], dict):
            content_data = data["data"]
            if "content" in content_data:
                content = content_data["content"]
            elif "text" in content_data:
                content = content_data["text"]
            elif "comment" in content_data:
                content = content_data["comment"]
        
        # 生成标准化评论消息
        return {
            "type": "comment",
            "user": user,
            "content": content,
            "raw_data": data
        }
    
    def _parse_gift(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """解析礼物消息
        
        Args:
            data: 原始消息数据
            
        Returns:
            统一格式的礼物消息
        """
        # 提取用户信息
        user = self._extract_user_info(data)
        
        # 提取礼物信息
        gift_name = "未知礼物"
        gift_count = 1
        gift_value = 0
        
        if "gift" in data:
            gift_data = data["gift"]
            gift_name = gift_data.get("name", "未知礼物")
            gift_count = gift_data.get("count", 1)
            gift_value = gift_data.get("value", 0)
        elif "data" in data and isinstance(data["data"], dict):
            gift_data = data["data"]
            gift_name = gift_data.get("gift_name", gift_data.get("name", "未知礼物"))
            gift_count = gift_data.get("gift_count", gift_data.get("count", 1))
            gift_value = gift_data.get("gift_value", gift_data.get("value", 0))
        
        # 生成标准化礼物消息
        return {
            "type": "gift",
            "user": user,
            "gift_name": gift_name,
            "gift_count": gift_count,
            "gift_value": gift_value,
            "raw_data": data
        }
    
    def _parse_enter(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """解析进入直播间消息
        
        Args:
            data: 原始消息数据
            
        Returns:
            统一格式的进入消息
        """
        # 提取用户信息
        user = self._extract_user_info(data)
        
        # 生成标准化进入消息
        return {
            "type": "enter",
            "user": user,
            "raw_data": data
        }
    
    def _parse_like(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """解析点赞消息
        
        Args:
            data: 原始消息数据
            
        Returns:
            统一格式的点赞消息
        """
        # 提取用户信息
        user = self._extract_user_info(data)
        
        # 提取点赞数量
        like_count = 1
        if "data" in data and isinstance(data["data"], dict):
            like_data = data["data"]
            if "count" in like_data:
                like_count = like_data["count"]
        
        # 生成标准化点赞消息
        return {
            "type": "like",
            "user": user,
            "like_count": like_count,
            "raw_data": data
        }
    
    def _parse_follow(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """解析关注消息
        
        Args:
            data: 原始消息数据
            
        Returns:
            统一格式的关注消息
        """
        # 提取用户信息
        user = self._extract_user_info(data)
        
        # 生成标准化关注消息
        return {
            "type": "follow",
            "user": user,
            "raw_data": data
        }
    
    def _extract_user_info(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """从消息中提取用户信息
        
        Args:
            data: 原始消息数据
            
        Returns:
            用户信息字典
        """
        user_info = {
            "id": "",
            "nickname": "匿名用户",
            "level": 0,
            "avatar": ""
        }
        
        # 直接包含用户信息
        if "user" in data and isinstance(data["user"], dict):
            user_data = data["user"]
            user_info["id"] = user_data.get("id", user_data.get("user_id", ""))
            user_info["nickname"] = user_data.get("nickname", user_data.get("name", "匿名用户"))
            user_info["level"] = user_data.get("level", 0)
            user_info["avatar"] = user_data.get("avatar", user_data.get("avatar_url", ""))
        
        # 嵌套在data字段中的用户信息
        elif "data" in data and isinstance(data["data"], dict):
            data_content = data["data"]
            
            # 直接在data中的用户信息
            user_info["id"] = data_content.get("user_id", "")
            user_info["nickname"] = data_content.get("nickname", data_content.get("user_name", "匿名用户"))
            
            # 嵌套在data.user中的用户信息
            if "user" in data_content and isinstance(data_content["user"], dict):
                user_data = data_content["user"]
                if not user_info["id"]:
                    user_info["id"] = user_data.get("id", user_data.get("user_id", ""))
                if user_info["nickname"] == "匿名用户":
                    user_info["nickname"] = user_data.get("nickname", user_data.get("name", "匿名用户"))
                user_info["level"] = user_data.get("level", 0)
                user_info["avatar"] = user_data.get("avatar", user_data.get("avatar_url", ""))
        
        return user_info

    def _clean_nickname(self, nickname: str) -> str:
        """
        清理用户昵称中的潜在问题字符，过滤纯数字和表情等不利于TTS的字符
        
        Args:
            nickname: 原始昵称
            
        Returns:
            清理后的昵称，如果清理后为空则返回"用户"
        """
        if not nickname or not self.config.get('clean_nickname', True):
            return nickname
            
        # 如果是纯数字昵称，直接返回"用户"
        if re.match(r'^\d+$', nickname):
            return "用户"
            
        # 移除表情符号和特殊Unicode字符
        cleaned = ''
        for char in nickname:
            # 检查字符类别，过滤表情和特殊符号
            if not unicodedata.category(char).startswith(('So', 'Sk', 'Cn')):
                # 保留字母、数字、基本标点和中日韩字符
                if re.match(r'[\w\s.,!?-_\u4e00-\u9fff]', char):
                    cleaned += char
        
        # 移除前导/尾随空白和过多的内部空白
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        # 长度检查，如果太长可能会影响TTS
        if len(cleaned) > 15:
            cleaned = cleaned[:15] + "..."
            
        return cleaned if cleaned else "用户" # 如果清理后为空则返回默认值
        
    def is_special_nickname(self, nickname: str) -> bool:
        """
        检查昵称是否包含特殊字符或是纯数字等特殊情况
        
        Args:
            nickname: 用户昵称
            
        Returns:
            如果是特殊昵称返回True，否则返回False
        """
        # 纯数字检查
        if re.match(r'^\d+$', nickname):
            return True
            
        # 表情符号检查
        for char in nickname:
            if unicodedata.category(char).startswith(('So', 'Sk')):
                return True
                
        # 太长的昵称
        if len(nickname) > 15:
            return True
            
        return False

    def process_message(self, raw_message: str) -> Optional[Dict[str, Any]]:
        """
        处理原始WebSocket消息
        
        Args:
            raw_message: 原始WebSocket消息字符串
            
        Returns:
            处理后的消息字典，如果消息无效则返回None
        """
        try:
            # 解析外层JSON
            message = json.loads(raw_message)
            msg_type = message.get('Type')

            # 根据允许的消息类型过滤
            allowed_types: List[int] = self.config.get('allowed_message_types', [])
            if msg_type not in allowed_types:
                self.logger.debug(f"忽略消息类型: {msg_type} (不在允许列表中: {allowed_types})")
                return None

            # --- 根据消息类型处理 ---
            processed_message = None
            if msg_type == 1: # 评论
                processed_message = self._process_comment(message)
            elif msg_type == 2: # 点赞
                processed_message = self._process_like(message)
            elif msg_type == 3: # 用户进入
                processed_message = self._process_user_enter(message)
            elif msg_type == 4: # 关注
                processed_message = self._process_follow(message)
            elif msg_type == 5: # 礼物
                processed_message = self._process_gift(message)
            elif msg_type == 6: # 统计信息
                processed_message = self._process_stats(message)
            else:
                self.logger.debug(f"未定义处理器的消息类型: {msg_type}")
                return None
                
            # 如果已连接到直播会话，则将处理后的消息传递给会话
            if processed_message and hasattr(self, 'live_session') and hasattr(self.live_session, 'process_message'):
                try:
                    self.live_session.process_message(processed_message)
                except Exception as e:
                    self.logger.error(f"转发消息到直播会话时出错: {e}")
                    
            return processed_message

        except json.JSONDecodeError as e:
            self.logger.error(f"JSON解析错误: {e} - Raw message: {raw_message[:200]}...")
            return None
        except Exception as e:
            self.logger.error(f"消息处理错误: {e} - Raw: {raw_message[:200]}...", exc_info=True)
            return None

    def _get_timestamp(self, data: Dict[str, Any]) -> int:
        """
        提取时间戳，优先使用MsgId
        
        Args:
            data: 包含时间戳的数据字典
            
        Returns:
            时间戳（毫秒）
        """
        return data.get('MsgId', int(datetime.now().timestamp() * 1000)) # 默认使用当前时间戳

    def _get_common_data(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        解析通用的'Data'字段
        
        Args:
            message: 原始消息字典
            
        Returns:
            解析后的数据字典，解析失败则返回None
        """
        data_str = message.get('Data')
        if not data_str:
            self.logger.warning(f"消息类型 {message.get('Type')} 缺少 'Data' 字段")
            return None
        try:
            return json.loads(data_str)
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON解析错误 in Data field: {e} - Data: {data_str[:200]}...")
            return None

    def _is_valid_content(self, content: str) -> bool:
        """
        检查内容是否包含黑名单关键字
        
        Args:
            content: 需要检查的内容
            
        Returns:
            如果内容有效则返回True，否则返回False
        """
        if not self.config.get('filter_comments', True):
            return True
            
        for keyword in BLACKLIST_KEYWORDS:
            if keyword in content:
                self.logger.debug(f"内容包含黑名单关键词 '{keyword}': {content[:50]}...")
                return False
                
        return True

    # --- 特定消息类型的处理器 ---

    def _process_comment(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        处理类型1（评论）消息
        
        Args:
            message: 原始消息字典
            
        Returns:
            处理后的评论消息字典，无效则返回None
        """
        data = self._get_common_data(message)
        if not data: return None

        try:
            user_data = data.get('User', {})
            nickname = self._clean_nickname(user_data.get('Nickname'))
            content = data.get('Content', '')

            # 应用内容过滤
            if not self._is_valid_content(content):
                self.logger.debug(f"已过滤评论 (来自 '{nickname}'): {content[:50]}...")
                return None

            # 应用用户过滤
            if not self._passes_user_filters(user_data, nickname):
                return None

            return {
                'type': 'comment',
                'user': {
                    'id': user_data.get('Id'),
                    'nickname': nickname,
                    'level': user_data.get('Level', 0),
                },
                'content': content,
                'timestamp': self._get_timestamp(data)
            }
        except KeyError as e:
            self.logger.error(f"评论消息格式错误，缺少键: {e}")
            return None
        except Exception as e:
            self.logger.error(f"处理评论消息时错误: {e}", exc_info=True)
            return None

    def _process_like(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        处理类型2（点赞）消息
        
        Args:
            message: 原始消息字典
            
        Returns:
            处理后的点赞消息字典，无效则返回None
        """
        # 注意：点赞消息可能成批出现，后续可能需要聚合处理
        data = self._get_common_data(message)
        if not data: return None

        try:
            user_data = data.get('User', {})
            nickname = self._clean_nickname(user_data.get('Nickname'))

            # 应用用户过滤
            if not self._passes_user_filters(user_data, nickname):
                return None

            return {
                'type': 'like',
                'user': {
                    'id': user_data.get('Id'),
                    'nickname': nickname,
                    'level': user_data.get('Level', 0),
                },
                # 'count': data.get('Count', 1), # 假设存在Count字段表示单次点赞数
                'total_likes_in_message': data.get('Total'), # 来自用户示例的字段名
                'timestamp': self._get_timestamp(data)
            }
        except KeyError as e:
            self.logger.error(f"点赞消息格式错误，缺少键: {e}")
            return None
        except Exception as e:
            self.logger.error(f"处理点赞消息时错误: {e}", exc_info=True)
            return None

    def _passes_user_filters(self, user_data: Dict[str, Any], cleaned_nickname: str) -> bool:
        """
        应用通用的用户过滤规则
        
        Args:
            user_data: 用户数据字典
            cleaned_nickname: 已清理的用户昵称
            
        Returns:
            如果用户通过所有过滤规则则返回True，否则返回False
        """
        # 移除等级过滤，始终返回 True 以显示所有用户
        # 只保留基本验证，确保有用户ID
        if not user_data.get('Id'):
             self.logger.warning(f"消息缺少用户ID: {user_data}")
             return False
        return True

    def _process_user_enter(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        处理类型3（用户进入）消息
        
        Args:
            message: 原始消息字典
            
        Returns:
            处理后的用户进入消息字典，无效则返回None
        """
        data = self._get_common_data(message)
        if not data: return None

        try:
            # 提取用户信息
            user_data = data.get('User', {})
            nickname = self._clean_nickname(user_data.get('Nickname'))

            # 应用用户过滤
            if not self._passes_user_filters(user_data, nickname):
                return None

            # --- 提取其他关键信息 ---
            owner_data = data.get('Owner', data.get('Onwer', {})) # 注意：原始数据中可能存在拼写错误('Onwer')
            content = data.get('Content', '') # 原始内容可能包含"$来了"等

            processed_message = {
                'type': 'user_enter',
                'user': {
                    'id': user_data.get('Id'),
                    'nickname': nickname, # 使用经过清理的昵称
                    'original_nickname': user_data.get('Nickname'), # 保留原始昵称
                    'display_id': user_data.get('DisplayId'),
                    'level': user_data.get('Level', 0),
                    'follower_count': user_data.get('FollowerCount', 0),
                    'gender': user_data.get('Gender'),
                    'is_admin': user_data.get('IsAdmin', False),
                    'is_anchor': user_data.get('IsAnchor', False),
                },
                'room': {
                    'id': data.get('RoomId'),
                    'current_count': data.get('CurrentCount'),
                    'owner_nickname': owner_data.get('Nickname')
                },
                'original_content': content,
                'timestamp': self._get_timestamp(data)
            }

            # 最终验证 (允许缺少房间ID，但记录警告)
            if not processed_message['room']['id']:
                 self.logger.warning(f"用户进入消息缺少房间ID: {data}")
                 # 不再返回 None，继续处理消息

            self.logger.debug(f"成功处理用户进入消息，用户: {nickname}")
            return processed_message

        except KeyError as e:
            self.logger.error(f"用户进入消息格式错误，缺少键: {e}")
            return None
        except Exception as e:
            self.logger.error(f"处理用户进入消息时错误: {e}", exc_info=True)
            return None

    def _process_follow(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        处理类型4（关注）消息
        
        Args:
            message: 原始消息字典
            
        Returns:
            处理后的关注消息字典，无效则返回None
        """
        data = self._get_common_data(message)
        if not data: return None

        try:
            user_data = data.get('User', {})
            nickname = self._clean_nickname(user_data.get('Nickname'))

            # 应用用户过滤
            if not self._passes_user_filters(user_data, nickname):
                return None

            return {
                'type': 'follow',
                'user': {
                    'id': user_data.get('Id'),
                    'nickname': nickname,
                    'level': user_data.get('Level', 0),
                },
                'timestamp': self._get_timestamp(data)
            }
        except KeyError as e:
            self.logger.error(f"关注消息格式错误，缺少键: {e}")
            return None
        except Exception as e:
            self.logger.error(f"处理关注消息时错误: {e}", exc_info=True)
            return None

    def _process_gift(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        处理类型5（礼物）消息
        
        Args:
            message: 原始消息字典
            
        Returns:
            处理后的礼物消息字典，无效则返回None
        """
        # 注意：礼物消息可能需要合并连击
        data = self._get_common_data(message)
        if not data: return None

        try:
            user_data = data.get('User', {})
            nickname = self._clean_nickname(user_data.get('Nickname'))

            # 应用用户过滤
            if not self._passes_user_filters(user_data, nickname):
                return None

            # 如果需要，可以添加礼物名称的映射
            gift_name = data.get("GiftName", "未知礼物") # 如果名称缺失则使用默认值

            return {
                'type': 'gift',
                'user': {
                    'id': user_data.get('Id'),
                    'nickname': nickname,
                    'level': user_data.get('Level', 0),
                },
                'gift_name': gift_name,
                'count': data.get("GiftCount", 1),
                'diamonds': data.get("DiamondCount", 0), # 礼物价值（抖币/钻石）
                'timestamp': self._get_timestamp(data)
            }
        except KeyError as e:
            self.logger.error(f"礼物消息格式错误，缺少键: {e}")
            return None
        except Exception as e:
            self.logger.error(f"处理礼物消息时错误: {e}", exc_info=True)
            return None

    def _process_stats(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        处理类型6（直播间统计信息）消息
        
        Args:
            message: 原始消息字典
            
        Returns:
            处理后的统计信息消息字典，无效则返回None
        """
        # 这些可能是频率较低的系统消息
        data = self._get_common_data(message)
        if not data: return None

        try:
            return {
                'type': 'stats',
                'online_count': data.get("OnlineUserCount"),
                'total_user_count': data.get("TotalUserCount"), # 累计？
                'timestamp': self._get_timestamp(data)
            }
        except KeyError as e:
            self.logger.error(f"统计消息格式错误，缺少键: {e}")
            return None
        except Exception as e:
            self.logger.error(f"处理统计消息时错误: {e}", exc_info=True)
            return None

    def analyze_template(self, template: str) -> Dict[str, Any]:
        """
        分析模板结构
        
        Args:
            template: 模板文本
            
        Returns:
            包含模板分析结果的字典
        """
        # 计算选项和变体数量
        option_pattern = r'\{([^{}]*)\}'
        options = re.findall(option_pattern, template)
        
        variant_count = len(options)
        all_choices = []
        
        for option in options:
            choices = option.split('|')
            all_choices.append(len(choices))
        
        max_options = max(all_choices) if all_choices else 0
        avg_options = sum(all_choices) / len(all_choices) if all_choices else 0
        
        # 估计潜在组合数
        potential_combinations = 1
        for choice_count in all_choices:
            potential_combinations *= choice_count
            
        # 检测嵌套选项 (还可以进一步完善)
        nested_pattern = r'\{[^{}]*\{[^{}]*\}[^{}]*\}'
        nested_count = len(re.findall(nested_pattern, template))
        
        return {
            'variant_count': variant_count,
            'option_count': sum(all_choices),
            'average_options': round(avg_options, 2),
            'max_options': max_options,
            'nested_count': nested_count,
            'potential_combinations': potential_combinations,
        }
