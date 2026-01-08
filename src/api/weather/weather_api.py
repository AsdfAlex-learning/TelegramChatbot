import logging
from src.api.base.base_api import BaseAPI

class WeatherAPI(BaseAPI):
    def get_data(self, city: str):
        if not self.enabled:
            return "Weather API is disabled."
        
        # 模拟 API 调用
        api_key = self.config.get("api_key")
        base_url = self.config.get("base_url")
        
        logging.info(f"Fetching weather for {city} using {base_url} with key {api_key[:4]}***")
        
        # 这里可以替换为真实的 requests.get 调用
        return f"Weather in {city}: Sunny, 25°C (Simulated Data from {self.name})"
