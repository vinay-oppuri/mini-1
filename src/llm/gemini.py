from google.genai import Client
import os

client = Client(
    api_key="AIzaSyBl13uJxn48ciGe44rREtLrNu-s1bK9Kkk"
)

response = client.models.generate_content(
    model="gemini-3-flash-preview",
    contents="what is price of gold in rupees of 10 grams?"
)

print(response.text)
