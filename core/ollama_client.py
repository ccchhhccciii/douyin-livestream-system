import requests
import json
import logging
import time # Import time for potential retry delay

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class OllamaClient:
    """
    A client for interacting with a local Ollama API endpoint.
    Implements basic error handling and retry logic.
    """
    # Removed default values for base_url and model - must be provided during instantiation
    def __init__(self, base_url: str, model: str, timeout: int = 60, max_retries: int = 3):
        """
        Initializes the OllamaClient.

        Args:
            base_url (str): The base URL of the Ollama API endpoint (e.g., "http://localhost:11434").
            model (str): The Ollama model to use (e.g., "qwen2.5:14b").
            timeout (int): Request timeout in seconds. Defaults to 60.
            max_retries (int): Maximum number of retries on connection errors. Defaults to 3.
        """
        if not base_url:
            raise ValueError("Base URL cannot be empty.")
        if not model:
            raise ValueError("Model name cannot be empty.")
        self.base_url = base_url.rstrip('/')
        self.generate_url = f"{self.base_url}/api/generate"
        self.default_model = model
        self.timeout = timeout
        self.max_retries = max_retries
        logging.info(f"OllamaClient initialized: URL='{self.base_url}', Model='{self.default_model}', Timeout={self.timeout}, Retries={self.max_retries}")

    def generate_completion(self, prompt: str, model: str = None) -> str | None:
        """
        Generates text completion using the Ollama API with retry logic.

        Args:
            prompt (str): The input prompt for the language model.
            model (str, optional): The specific model to use. Defaults to self.default_model.

        Returns:
            str | None: The generated text completion, or None if an error occurs after retries.
        """
        if not prompt:
            logging.warning("Generate completion called with empty prompt.")
            return None

        target_model = model if model else self.default_model
        payload = {
            "model": target_model,
            "prompt": prompt,
            "stream": False  # Keep stream False for simpler handling initially
        }
        headers = {'Content-Type': 'application/json'}

        logging.info(f"Sending request to Ollama: model='{target_model}', prompt='{prompt[:50]}...'")

        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    self.generate_url,
                    headers=headers,
                    data=json.dumps(payload),
                    timeout=180 # Increased timeout to 180 seconds (3 minutes)
                )
                response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)

                # Parse the JSON response
                result = response.json()
                generated_text = result.get('response')

                if generated_text:
                    logging.info(f"Received response from Ollama (attempt {attempt + 1}): '{generated_text[:100]}...'")
                    return generated_text.strip()
                else:
                    # Log error if 'response' field is missing but request was successful (2xx)
                    logging.error(f"Ollama response missing 'response' field (attempt {attempt + 1}). Full response: {result}")
                    return None # Don't retry if the response format is wrong

            except requests.exceptions.ConnectionError as e:
                logging.warning(f"Connection error on attempt {attempt + 1}/{self.max_retries}: {e}")
                if attempt == self.max_retries - 1:
                    logging.error("Max retries reached for connection error.")
                    return None
                # Optional: Add a small delay before retrying
                # time.sleep(1)
            except requests.exceptions.Timeout as e:
                logging.warning(f"Request timed out on attempt {attempt + 1}/{self.max_retries}: {e}")
                if attempt == self.max_retries - 1:
                    logging.error("Max retries reached for timeout error.")
                    return None
            except requests.exceptions.RequestException as e:
                # Catch other request-related errors (like HTTPError)
                logging.error(f"Request failed (attempt {attempt + 1}): {e}")
                # Depending on the error type, you might choose not to retry immediately
                return None # Don't retry on general request errors like 4xx/5xx

        return None # Should not be reached if loop completes, but added for safety

    def generate_completion_stream(self, prompt: str, model: str = None):
        """
        Generates text completion using the Ollama API and yields response chunks.

        Args:
            prompt (str): The input prompt for the language model.
            model (str, optional): The specific model to use. Defaults to self.default_model.

        Yields:
            str: Chunks of the generated text response.

        Raises:
            requests.exceptions.RequestException: If a request error occurs.
            json.JSONDecodeError: If response chunk is not valid JSON.
            Exception: For other potential errors during streaming.
        """
        if not prompt:
            logging.warning("Generate completion stream called with empty prompt.")
            return

        target_model = model if model else self.default_model
        payload = {
            "model": target_model,
            "prompt": prompt,
            "stream": True # Enable streaming
        }
        headers = {'Content-Type': 'application/json'}

        logging.info(f"Sending streaming request to Ollama: model='{target_model}', prompt='{prompt[:50]}...'")

        try:
            # Use stream=True in requests.post
            response = requests.post(
                self.generate_url,
                headers=headers,
                data=json.dumps(payload),
                timeout=180, # Keep increased timeout
                stream=True # Enable streaming in requests
            )
            response.raise_for_status()

            # Process the stream line by line
            for line in response.iter_lines():
                if line:
                    try:
                        chunk = json.loads(line.decode('utf-8'))
                        response_part = chunk.get('response')
                        if response_part:
                            yield response_part # Yield the text part of the chunk
                        # Check if generation is done (optional, based on Ollama stream format)
                        if chunk.get('done'):
                            logging.info("Ollama stream finished.")
                            break
                    except json.JSONDecodeError:
                        logging.error(f"Failed to decode JSON chunk from stream: {line}")
                        # Decide whether to continue or raise
                        continue # Skip malformed lines for now
                    except Exception as chunk_e:
                         logging.error(f"Error processing stream chunk: {chunk_e}")
                         raise # Re-raise other chunk processing errors

        except requests.exceptions.RequestException as e:
            logging.error(f"Streaming request failed: {e}")
            raise # Re-raise request exceptions
        except Exception as e:
            logging.exception("An unexpected error occurred during streaming.")
            raise # Re-raise other unexpected errors


# Example Usage (Optional - can be removed or kept for testing)
if __name__ == '__main__':
    client = OllamaClient()
    test_prompt = "请给我写一个关于智能手表的简短描述。"
    completion = client.generate_completion(test_prompt)
    if completion:
        print("\n--- Test Completion ---")
        print(completion)
        print("----------------------")
    else:
        print("\n--- Test Failed ---")
        print("Could not get completion from Ollama.")
        print("-------------------")
