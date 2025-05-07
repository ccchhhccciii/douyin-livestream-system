import os
import logging
import configparser
import time
from volcenginesdkarkruntime import Ark # Re-importing the SDK, removing ArkError

# Configure basic logging for the client
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - VolcengineClient - %(message)s')

# Calculate project root dynamically to find config.ini
# This file is in core/ directly under project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE_PATH = os.path.join(project_root, "config.ini")

class VolcengineClient:
    """
    Client for interacting with the Volcengine Ark API (Doubao models) via the SDK.
    Attempts to initialize using api_key from config.ini based on SDK assertion.
    """
    def __init__(self):
        """
        Initializes the VolcengineClient using the Ark SDK.
        Reads api_key from config.ini and passes it to the Ark constructor.
        """
        self.client = None
        api_key = None
        try:
            config = configparser.ConfigParser()
            if not os.path.exists(CONFIG_FILE_PATH):
                logging.error(f"配置文件未找到: {CONFIG_FILE_PATH}. 无法读取 Volcengine API Key。")
                # Raise error immediately as SDK requires the key explicitly based on AssertionError
                raise FileNotFoundError(f"Config file not found at {CONFIG_FILE_PATH}, cannot initialize VolcengineClient.")
            else:
                config.read(CONFIG_FILE_PATH, encoding='utf-8')
                logging.info(f"从 {CONFIG_FILE_PATH} 加载 Volcengine 配置")
                if 'Volcengine' in config and 'api_key' in config['Volcengine']:
                    api_key = config['Volcengine'].get('api_key') # Use .get for safety
                    if api_key:
                        logging.info("从配置文件中读取到 Volcengine API Key。")
                    else:
                        logging.error("配置文件 [Volcengine] 部分的 api_key 为空。")
                        raise ValueError("Volcengine API Key is empty in config.ini")
                else:
                    logging.error("配置文件中未找到 [Volcengine] 部分或 api_key。")
                    raise ValueError("Volcengine API Key not found in config.ini under [Volcengine] section.")

            # Initialize the Ark client.
            # Based on the latest AssertionError, we MUST pass api_key or ak/sk.
            # We are passing the api_key read from config.ini.
            logging.info("Initializing Volcengine Ark SDK client (using api_key from config.ini)...")
            self.client = Ark(api_key=api_key) # Pass the key directly
            logging.info("VolcengineClient (SDK) 初始化成功。")

        # Removed specific ArkError catch due to ImportError
        # except ArkError as e:
        #     logging.error(f"初始化 Volcengine Ark SDK 时发生 ArkError: {getattr(e, 'code', 'N/A')}, {getattr(e, 'message', str(e))}")
        #     # Potentially check for specific error codes related to auth failure
        #     if "authenticate" in getattr(e, 'message', '').lower() or getattr(e, 'code', '') == "Unauthorized":
        #          logging.error("认证失败。请检查 VOLC_ACCESSKEY 和 VOLC_SECRETKEY 环境变量是否已正确设置。")
        #     raise Exception(f"Failed to initialize Volcengine SDK: {e}") from e
        except Exception as e:
            # Catching generic Exception as ArkError is not available for import
            logging.exception("初始化 VolcengineClient (SDK) 时发生错误。")
            # Attempt to check common attributes for auth errors, though they might not exist
            if "authenticate" in str(e).lower() or "unauthorized" in str(e).lower():
                 logging.error("初始化错误可能与认证有关。请检查 VOLC_ACCESSKEY 和 VOLC_SECRETKEY 环境变量是否已正确设置。")
            raise Exception(f"Failed to initialize Volcengine SDK: {e}") from e

    def generate_completion(self, model: str, prompt: str, system_prompt: str = "你是豆包，是由字节跳动开发的 AI 人工智能助手", max_tokens: int = 4096):
        """
        Generates a completion using the specified Volcengine model via SDK.

        Args:
            model (str): The model ID (endpoint_id) to use.
            prompt (str): The user prompt.
            system_prompt (str): The system message content.
            max_tokens (int): The maximum number of tokens to generate.

        Returns:
            str: The generated text content.
            None: If an error occurs during generation.
        """
        if not self.client:
            logging.error("Volcengine SDK client 未初始化。")
            return None

        try:
            logging.info(f"向 Volcengine SDK (模型: {model}) 发送非流式请求...")
            # Using the documented chat completions endpoint via SDK
            completion = self.client.chat.completions.create(
                model=model, # SDK uses 'model' parameter which maps to endpoint_id
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                # stream=False is default
                temperature=0.7,
                top_p=0.9,
                max_tokens=max_tokens
            )
            logging.info(f"从 Volcengine SDK (模型: {model}) 收到响应。")

            if completion.choices and completion.choices[0].message:
                content = completion.choices[0].message.content
                # Log token usage if available
                usage = completion.usage
                if usage:
                     logging.info(f"Token usage: Prompt={usage.prompt_tokens}, Completion={usage.completion_tokens}, Total={usage.total_tokens}")
                return content.strip() if content else None
            else:
                logging.error(f"Volcengine SDK 响应格式不符合预期: {completion}")
                return None

        # Removed specific ArkError catch due to ImportError
        # except ArkError as e:
        #     logging.error(f"调用 Volcengine SDK 时发生 ArkError (类型: {type(e).__name__}, 模型: {model}): {getattr(e, 'code', 'N/A')}, {getattr(e, 'message', str(e))}")
        #     # Check for specific errors like authentication or rate limits
        #     if getattr(e, 'code', '') == "Unauthorized":
        #          logging.error("SDK 认证失败。请再次检查环境变量。")
        #     elif "quota" in getattr(e, 'message', '').lower() or "limit" in getattr(e, 'message', '').lower():
        #          logging.error("可能已达到 API 配额或速率限制。")
        #     return None
        except AttributeError as e:
             logging.error(f"调用 Volcengine SDK 时发生 AttributeError (模型: {model}): {e}")
             logging.error("这通常意味着 SDK 客户端未能正确初始化 (可能由于环境变量问题) 或 SDK 版本与预期不符。")
             return None
        except Exception as e:
            logging.exception(f"调用 Volcengine SDK 时发生未知错误 (类型: {type(e).__name__}, 模型: {model})。")
            return None

    def generate_completion_stream(self, model: str, prompt: str, system_prompt: str = "你是豆包，是由字节跳动开发的 AI 人工智能助手", max_tokens: int = 4096):
        """
        Generates a completion using the specified Volcengine model via SDK and yields response chunks.

        Args:
            model (str): The model ID (endpoint_id) to use.
            prompt (str): The user prompt.
            system_prompt (str): The system message content.
            max_tokens (int): The maximum number of tokens to generate (may not be respected by all stream endpoints).

        Yields:
            str: Chunks of the generated text content.

        Raises:
            Exception: If a critical SDK error occurs during the request setup or streaming.
        """
        if not self.client:
            logging.error("Volcengine SDK client 未初始化。")
            # Raise an exception or return an empty generator? Raising is clearer.
            raise Exception("Volcengine SDK client not initialized.")

        try:
            logging.info(f"向 Volcengine SDK (模型: {model}) 发送流式请求...")
            # Using the documented chat completions stream endpoint via SDK
            stream = self.client.chat.completions.create(
                model=model, # SDK uses 'model' parameter which maps to endpoint_id
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                stream=True,
                # Add other parameters like temperature, top_p if needed
            )
            logging.info(f"开始接收来自 Volcengine SDK (模型: {model}) 的流式响应。")

            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta:
                    content_chunk = chunk.choices[0].delta.content
                    if content_chunk:
                        yield content_chunk
                # Handle potential final usage info if needed (check SDK stream object details)
                # elif chunk.usage:
                #     usage = chunk.usage
                #     logging.info(f"Final Token usage: Prompt={usage.prompt_tokens}, Completion={usage.completion_tokens}, Total={usage.total_tokens}")


            logging.info(f"Volcengine SDK (模型: {model}) 流式响应接收完毕。")

        # Removed specific ArkError catch due to ImportError
        # except ArkError as e:
        #     logging.error(f"处理 Volcengine SDK 流时发生 ArkError (类型: {type(e).__name__}, 模型: {model}): {getattr(e, 'code', 'N/A')}, {getattr(e, 'message', str(e))}")
        #     # Check for specific errors
        #     if getattr(e, 'code', '') == "Unauthorized":
        #          logging.error("SDK 认证失败。请再次检查环境变量。")
        #     # Re-raise to signal failure to the worker
        #     raise Exception(f"Volcengine SDK stream error: {e}") from e
        except AttributeError as e:
             logging.error(f"处理 Volcengine SDK 流时发生 AttributeError (模型: {model}): {e}")
             logging.error("这通常意味着 SDK 客户端未能正确初始化 (可能由于环境变量问题) 或 SDK 版本与预期不符。")
             raise Exception(f"Volcengine SDK stream AttributeError: {e}") from e
        except Exception as e:
            logging.exception(f"处理 Volcengine SDK 流时发生未知错误 (类型: {type(e).__name__}, 模型: {model})。")
            # Re-raise to signal failure to the worker
            raise Exception(f"Unknown error during Volcengine SDK stream: {e}") from e


# Example Usage (for testing purposes, relies on ENV VARS)
if __name__ == '__main__':
    # IMPORTANT: Set VOLC_ACCESSKEY and VOLC_SECRETKEY environment variables before running this.
    print("确保已设置 VOLC_ACCESSKEY 和 VOLC_SECRETKEY 环境变量！")
    try:
        client = VolcengineClient()

        test_prompt = "写一首关于夏天的短诗"
        test_model = "doubao-pro-32k" # Replace with a valid model endpoint_id from Volcengine

        print("\n--- Volcengine SDK Non-Stream Test ---")
        response_text = client.generate_completion(model=test_model, prompt=test_prompt)
        if response_text:
            print(response_text)
        else:
            print("未能从 Volcengine SDK 获取非流式响应。")
        print("--------------------------------------\n")

        print("\n--- Volcengine SDK Stream Test ---")
        try:
            full_stream_response = ""
            for chunk in client.generate_completion_stream(model=test_model, prompt=test_prompt):
                print(chunk, end='', flush=True)
                full_stream_response += chunk
            print("\nStream finished.")
        except Exception as stream_err:
             print(f"\n流式测试中发生错误: {stream_err}")
        print("----------------------------------\n")

    except Exception as e:
        print(f"示例用法中发生错误: {e}")
