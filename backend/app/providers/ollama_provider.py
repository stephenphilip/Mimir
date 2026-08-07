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
            "stream": True,
            # Keep model warm between turns — major latency win on CPU
            "keep_alive": "30m",
            "options": {
                # Bound runaway generations without cutting normal Excel/code replies
                "num_predict": 3072,
                "temperature": 0.35,
                "num_ctx": 8192,
            },
        }
        if system_prompt:
            payload["system"] = system_prompt

        try:
            # (connect timeout, read timeout). None read = stream until Ollama finishes.
            # Previous hard 60s timeout aborted CPU generations mid-reply → broken/hallucinated answers.
            response = requests.post(url, json=payload, stream=True, timeout=(10, None))
            if response.status_code != 200:
                yield "Error: Ollama returned status code {}. Is the model pulled?".format(
                    response.status_code
                )
                return

            for line in response.iter_lines():
                if line:
                    chunk = json.loads(line.decode("utf-8"))
                    if chunk.get("error"):
                        yield "Error from Ollama: {}".format(chunk.get("error"))
                        return
                    text = chunk.get("response", "")
                    if text:
                        yield text
                    if chunk.get("done", False):
                        break
        except requests.exceptions.ConnectionError:
            yield "Error connecting to Ollama. Start Ollama and ensure it is running on localhost:11434."
        except Exception as e:
            yield "Error connecting to Ollama: {}".format(str(e))

    def generate(self, model: str, prompt: str, system_prompt: Optional[str] = None) -> str:
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": "30m",
            "options": {
                "num_predict": 3072,
                "temperature": 0.35,
                "num_ctx": 8192,
            },
        }
        if system_prompt:
            payload["system"] = system_prompt

        try:
            response = requests.post(url, json=payload, timeout=(10, 600))
            if response.status_code == 200:
                return response.json().get("response", "")
            return "Error: Ollama returned status code {}".format(response.status_code)
        except Exception as e:
            return "Error connecting to Ollama: {}".format(str(e))

    def get_embeddings(self, text: str, model: Optional[str] = None) -> List[float]:
        raise NotImplementedError("Embeddings generation is not supported in the MVP Ollama provider.")

    def generate_vision(
        self,
        model: str,
        prompt: str,
        image_paths: List[str],
        system_prompt: Optional[str] = None,
    ) -> Generator[str, None, None]:
        raise NotImplementedError("Vision generation is not supported in the MVP Ollama provider.")

    def generate_json(
        self,
        model: str,
        prompt: str,
        schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "keep_alive": "30m",
            "options": {
                "num_predict": 1024,
                "temperature": 0.1,
                "num_ctx": 8192,
            },
        }
        
        # Include schema in system prompt if provided
        final_system = system_prompt or ""
        if schema:
            final_system += f"\n\nYou MUST respond in JSON format matching this schema:\n{json.dumps(schema)}"
            
        if final_system:
            payload["system"] = final_system

        try:
            response = requests.post(url, json=payload, timeout=(10, 60))
            if response.status_code == 200:
                result_text = response.json().get("response", "{}")
                return json.loads(result_text)
            raise Exception(f"Ollama returned status code {response.status_code}")
        except Exception as e:
            raise Exception(f"Error connecting to Ollama: {str(e)}")

    def call_tools(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        raise NotImplementedError("Native tool calling is not supported in the MVP Ollama provider.")

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "provider_name": "ollama",
            "base_url": self.base_url,
        }
