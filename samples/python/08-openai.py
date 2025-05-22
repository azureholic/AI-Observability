import asyncio
from openai import AsyncAzureOpenAI
from dotenv import load_dotenv
import os
# Load environment variables from .env file
load_dotenv()

# gets API Key from environment variable OPENAI_API_KEY
endpoint = os.environ.get("AZURE_AIGW_ENDPOINT")
api_key = os.environ.get("AZURE_AIGW_API_KEY")
client = AsyncAzureOpenAI(azure_endpoint = endpoint,api_key=api_key,api_version="2024-10-21")

async def main() -> None:
    for i in range(20):
        print("Iteration:", i)
        # Call the chat completion API
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages = [ {"role": "user", "content": "How many feet are in a mile?"} ]
        )

        print(response.choices[0].message.content)

asyncio.run(main())