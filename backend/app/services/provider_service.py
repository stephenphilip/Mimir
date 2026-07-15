import json
import requests
from typing import Generator

class AIProvider:
    def generate_stream(self, model: str, prompt: str, system_prompt: str = None) -> Generator[str, None, None]:
        raise NotImplementedError()

    def generate(self, model: str, prompt: str, system_prompt: str = None) -> str:
        raise NotImplementedError()

class OllamaProvider(AIProvider):
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url

    def generate_stream(self, model: str, prompt: str, system_prompt: str = None) -> Generator[str, None, None]:
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

    def generate(self, model: str, prompt: str, system_prompt: str = None) -> str:
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
