from google import genai
import os
import dotenv

dotenv.load_dotenv()

class GeminiClient:
    def __init__(self, model="gemini-2.5-flash"):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY not found.")
        self.client = genai.Client(api_key=api_key)
        self.model = model

    def generate(self, prompt: str) -> str:
        response = self.client.models.generate_content(
            model = self.model,
            contents= prompt,
        )
        return response.text