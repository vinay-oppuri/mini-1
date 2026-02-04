from llm.gemini import GeminiClient

if __name__ == "__main__":
    llm = GeminiClient()
    reply = llm.generate("Who is the current president of the USA as of 2026?")
    print("Gemini responce: ", reply)