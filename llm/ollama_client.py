"""
Ollama LLM Client
Handles all communication with the Ollama API
"""

import time
import requests
from typing import Optional, Dict, Any


class OllamaClient:
    """Client for interacting with Ollama API"""
    
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "mistral"):
        self.base_url = base_url
        self.model = model
        self.generate_url = f"{base_url}/api/generate"
    
    def configure(self, base_url: Optional[str] = None, model: Optional[str] = None) -> None:
        """
        Configure the Ollama client
        
        Args:
            base_url: Ollama API URL
            model: Model to use
        """
        if base_url:
            self.base_url = base_url
            self.generate_url = f"{base_url}/api/generate"
        if model:
            self.model = model
    
    def send_prompt(self, prompt: str, system_prompt: str = '') -> Dict[str, Any]:
        """
        Send a prompt to the Ollama API
        
        Args:
            prompt: The prompt to send
            system_prompt: Optional system prompt
            
        Returns:
            Response with text, response_time, and tokens_used
        """
        start_time = time.time()
        
        # Combine system prompt with user prompt if provided
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        
        try:
            response = requests.post(
                self.generate_url,
                json={
                    "model": self.model,
                    "prompt": full_prompt,
                    "stream": False
                },
                headers={"Content-Type": "application/json"}
            )
            
            if not response.ok:
                raise Exception(
                    f"Ollama error: {response.status_code} - "
                    "Make sure Ollama is running. Download from https://ollama.ai"
                )
            
            data = response.json()
            response_time = int((time.time() - start_time) * 1000)  # Convert to ms
            tokens_used = data.get('eval_count', 0)
            
            if not data.get('response'):
                raise Exception("No response from Ollama")
            
            return {
                'text': data['response'],
                'response_time': response_time,
                'tokens_used': tokens_used
            }
            
        except requests.exceptions.ConnectionError:
            raise Exception(
                "Cannot connect to Ollama. Make sure Ollama is running. "
                "Download from https://ollama.ai"
            )
        except Exception as e:
            print(f"Ollama API error: {e}")
            raise
    
    def is_available(self) -> bool:
        """
        Check if Ollama is available
        
        Returns:
            True if Ollama is running, False otherwise
        """
        try:
            response = requests.get(f"{self.base_url}/api/tags")
            return response.ok
        except:
            return False


# Singleton instance
ollama_client = OllamaClient()
