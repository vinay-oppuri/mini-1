from google import genai
import os
import dotenv
dotenv.load_dotenv()

client = genai.Client(api_key=os.getenv("GOOGLE_KEY"))

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Who is the current president of the USA as of 2026?",
)

print(response.text)
