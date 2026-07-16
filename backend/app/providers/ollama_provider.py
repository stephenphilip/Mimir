import json
import requests
from typing import Generator, List, Dict, Any, Optional

from ..interfaces.providers import IProvider

class OllamaProvider(IProvider):
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url

    def generate_stream(self, model: str, prompt: str, system_prompt: Optional[str] = None) -> Generator[str, None, None]:
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": True
        }
        if system_prompt:
            payload["system"] = system_prompt
            
        try:
            response = requests.post(url, json=payload, stream=True, timeout=60)
            if response.status_code != 200:
                yield f"Error: Ollama returned status code {response.status_code}"
                return

            for line in response.iter_lines():
                if line:
                    chunk = json.loads(line.decode("utf-8"))
                    yield chunk.get("response", "")
                    if chunk.get("done", False):
                        break
        except Exception as e:
            yield f"Error connecting to Ollama: {str(e)}"

    def generate(self, model: str, prompt: str, system_prompt: Optional[str] = None) -> str:
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False
        }
        if system_prompt:
            payload["system"] = system_prompt
            
        try:
            response = requests.post(url, json=payload, timeout=60)
            if response.status_code == 200:
                return response.json().get("response", "")
            else:
                return f"Error: Ollama returned status code {response.status_code}"
        except Exception as e:
            return f"Error connecting to Ollama: {str(e)}"

    def get_embeddings(self, text: str, model: Optional[str] = None) -> List[float]:
        raise NotImplementedError("Embeddings generation is not supported in the MVP Ollama provider.")

    def generate_vision(
        self,
        model: str,
        prompt: str,
        image_paths: List[str],
        system_prompt: Optional[str] = None
    ) -> Generator[str, None, None]:
        raise NotImplementedError("Vision generation is not supported in the MVP Ollama provider.")

    def generate_json(
        self,
        model: str,
        prompt: str,
        schema: Dict[str, Any],
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        raise NotImplementedError("Structured JSON output is not supported in the MVP Ollama provider.")

    def call_tools(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        raise NotImplementedError("Native tool calling is not supported in the MVP Ollama provider.")

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "provider_name": "ollama",
            "base_url": self.base_url
        }
