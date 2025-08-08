import openai
import os

# Set the API key
openai.api_key = os.getenv("OPENAI_API_KEY")

# For summarization (using OpenAI)
def summarize_text(text):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Summarize this document"},
                {"role": "user", "content": text[:3000]}  # Trim to fit token limit
            ],
            temperature=0.5,
            max_tokens=200
        )
        return response.choices[0].message['content'].strip()
    except Exception as e:
        return f"Error in summarization: {e}"
