import logging
from typing import List, Dict, Any, Generator, Optional
from groq import Groq
from app.core.config import settings

logger = logging.getLogger("ai_service.llm")

class LLMService:
    """
    LLM completion and streaming service for LangGraph workflow nodes.
    Supports Google Gemini (via google-genai SDK), Groq, and NVIDIA NIM.
    """

    def __init__(self):
        self.provider = settings.LLM_PROVIDER
        self.groq_api_key = settings.GROQ_API_KEY
        self.gemini_api_key = settings.GEMINI_API_KEY
        self.nvidia_api_key = settings.NVIDIA_API_KEY
        self._groq_client: Optional[Groq] = None
        self._gemini_client: Optional[Any] = None

    @property
    def groq_client(self) -> Groq:
        if self._groq_client is None:
            if not self.groq_api_key:
                raise ValueError("GROQ_API_KEY is not configured.")
            self._groq_client = Groq(api_key=self.groq_api_key)
        return self._groq_client

    @property
    def gemini_client(self):
        if self._gemini_client is None:
            if not self.gemini_api_key:
                raise ValueError("GEMINI_API_KEY is not configured.")
            from google import genai
            self._gemini_client = genai.Client(api_key=self.gemini_api_key)
        return self._gemini_client

    def _should_use_gemini(self) -> bool:
        return (
            self.provider == "gemini"
            or (self.gemini_api_key is not None and len(self.gemini_api_key.strip()) > 10 and self.provider != "groq")
        )

    def _convert_messages_for_gemini(self, messages: List[Dict[str, str]]):
        """Converts OpenAI-style messages into system instruction + user prompt for Gemini."""
        system_chunks = []
        user_chunks = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role == "system":
                system_chunks.append(content)
            elif role == "user":
                user_chunks.append(content)
            else:
                user_chunks.append(f"{role.capitalize()}: {content}")

        system_instruction = "\n\n".join(system_chunks) if system_chunks else None
        contents = "\n\n".join(user_chunks) if user_chunks else "Hello"
        return system_instruction, contents

    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        model: Optional[str] = None
    ) -> str:
        """
        Synchronous / blocking generation for intermediate workflow nodes.
        """
        if self._should_use_gemini():
            try:
                from google.genai import types
                sys_inst, prompt_text = self._convert_messages_for_gemini(messages)
                target_model = model or settings.GEMINI_LLM_MODEL
                config = types.GenerateContentConfig(
                    temperature=temperature,
                    system_instruction=sys_inst
                )
                response = self.gemini_client.models.generate_content(
                    model=target_model,
                    contents=prompt_text,
                    config=config
                )
                return response.text or ""
            except Exception as e:
                logger.warning(f"Google Gemini generation failed: {e}. Falling back to Groq...")

        target_model = model or settings.GROQ_LLM_MODEL
        try:
            completion = self.groq_client.chat.completions.create(
                model=target_model,
                messages=messages,
                temperature=temperature,
                max_tokens=1024
            )
            return completion.choices[0].message.content or ""
        except Exception as e:
            logger.warning(f"Primary model {target_model} failed: {e}. Trying fallback 'openai/gpt-oss-120b'...")
            try:
                completion = self.groq_client.chat.completions.create(
                    model="openai/gpt-oss-120b",
                    messages=messages,
                    temperature=temperature,
                    max_tokens=1024
                )
                return completion.choices[0].message.content or ""
            except Exception as fallback_err:
                logger.error(f"Fallback model failed: {fallback_err}")
                raise fallback_err

    def stream_generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        model: Optional[str] = None
    ) -> Generator[str, None, None]:
        """
        Token-by-token streaming generator for grounded answer synthesis.
        """
        if self._should_use_gemini():
            try:
                from google.genai import types
                sys_inst, prompt_text = self._convert_messages_for_gemini(messages)
                target_model = model or settings.GEMINI_LLM_MODEL
                config = types.GenerateContentConfig(
                    temperature=temperature,
                    system_instruction=sys_inst
                )
                stream = self.gemini_client.models.generate_content_stream(
                    model=target_model,
                    contents=prompt_text,
                    config=config
                )
                for chunk in stream:
                    if chunk.text:
                        yield chunk.text
                return
            except Exception as e:
                logger.warning(f"Google Gemini streaming failed: {e}. Falling back to Groq...")

        target_model = model or settings.GROQ_LLM_MODEL
        try:
            stream = self.groq_client.chat.completions.create(
                model=target_model,
                messages=messages,
                temperature=temperature,
                stream=True
            )
            for chunk in stream:
                content = chunk.choices[0].delta.content or ""
                if content:
                    yield content
        except Exception as e:
            logger.warning(f"Streaming with {target_model} failed: {e}. Falling back to 'openai/gpt-oss-120b'...")
            stream = self.groq_client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=messages,
                temperature=temperature,
                stream=True
            )
            for chunk in stream:
                content = chunk.choices[0].delta.content or ""
                if content:
                    yield content

llm_service = LLMService()
