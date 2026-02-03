from comman import CommonUtils
import time 
from openai import OpenAI
import os

class AIReviewer(CommonUtils):
    def __init__(self, model_name: str = "gpt-4", max_tokens: int = 2048, env_path: str = ".env"):
        self.model_name = model_name
        self.max_tokens = max_tokens
        self.env_path = env_path
        
    def estimate_tokens(self,text: str, model: str = "gpt-4o") -> int:
        """
        Estimate token usage for OpenAI models.

        Args:
            text (str): Input text (prompt, diff, JSON, etc.)
            model (str): OpenAI model name (manual input)

        Returns:
            int: Estimated number of tokens
        """
        try:
            import tiktoken

            # Try exact tokenizer if available
            try:
                encoding = tiktoken.encoding_for_model(model)
            except KeyError:
                # Fallback encoding (most compatible)
                encoding = tiktoken.get_encoding("cl100k_base")

            return len(encoding.encode(text))

        except ImportError:
            # Hard fallback if tiktoken is not installed
            # Rule of thumb: 1 token ≈ 4 characters (English/code)
            return max(1, len(text) // 4)

    def call_openai(
        self,
        conversation: list,
        model: str,
        max_output_tokens: int = 1024,
        temperature: float = 0.0,
        timeout: int = 30,
        retries: int = 2
    ) -> str:
        """
        Low-level OpenAI call.
        Handles retries, timeouts, and strict response extraction.

        Args:
            conversation (list): Chat messages [{role, content}]
            model (str): OpenAI model name
            max_output_tokens (int): Max tokens for response
            temperature (float): Sampling temperature
            timeout (int): Request timeout in seconds
            retries (int): Number of retries on failure

        Returns:
            str: AI response text
        """

        api_key = self.get_env_value(self.env_path, "OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError("OPENAI_API_KEY is not set")

        client = OpenAI(api_key=api_key, timeout=timeout)

        last_error = None

        for attempt in range(1, retries + 1):
            try:
                print(f"The tokken estimation for the input is : {self.estimate_tokens(str(conversation),model=model)}")
                print(f"OpenAI call attempt {attempt}...")
                response = client.responses.create(
                    model=model,
                    input=[
                        {
                            "role": msg["role"],
                            "content": [{"type": "input_text", "text": msg["content"]}]
                        }
                        for msg in conversation
                    ],
                    max_output_tokens=max_output_tokens,
                    temperature=temperature
                )
                print("OpenAI call successful.")
                print(f"The tokken estimation for the output is : {self.estimate_tokens(str(response),model=model)}")

                # Extract text safely
                output_text = []
                if isinstance(response.output_text, str):
                    output_text.append(response.output_text)
                elif isinstance(response.output, list):
                    for item in response.output:
                            if item["type"] == "message":
                                for content in item["content"]:
                                    if content["type"] == "output_text":
                                        output_text.append(content["text"])
                
                if not output_text:
                    raise RuntimeError("Empty response from OpenAI")

                return "\n".join(output_text)

            except Exception as exc:
                last_error = exc
                if attempt < retries:
                    time.sleep(2 * attempt)
                else:
                    break

        raise RuntimeError(f"OpenAI call failed after {retries} attempts: {last_error}")
    
    def get_ai_response(
        self,
        conversation: list,
        model: str = "gpt-4.1",
        max_output_tokens: int = 1024
    ) -> str:
        """
        High-level AI helper.
        This is the only function your application should call.

        Args:
            conversation (list): Chat conversation
            model (str): OpenAI model
            max_output_tokens (int): Max tokens in AI output

        Returns:
            str: AI-generated response
        """

        if not isinstance(conversation, list) or not conversation:
            raise ValueError("Conversation must be a non-empty list")

        for msg in conversation:
            if "role" not in msg or "content" not in msg:
                raise ValueError("Each message must have 'role' and 'content'")

        return self.call_openai(
            conversation=conversation,
            model=model,
            max_output_tokens=max_output_tokens,
            temperature=0.0  # deterministic for PR / CI usage
        )