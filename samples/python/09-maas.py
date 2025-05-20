from azure.ai.inference import ChatCompletionsClient
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv
import os
# Load environment variables from .env file
load_dotenv()

# gets API Key from environment variable OPENAI_API_KEY
endpoint = os.environ.get("AZURE_AIGW_ENDPOINT")
api_key = os.environ.get("AZURE_AIGW_API_KEY")

if not api_key:
  raise Exception("A key should be provided to invoke the endpoint")

client = ChatCompletionsClient(
    endpoint=endpoint,
    credential=AzureKeyCredential(api_key)
)


model_info = client.get_model_info()
print("Model name:", model_info.model_name)
print("Model type:", model_info.model_type)
print("Model provider name:", model_info.model_provider_name)

payload = {
  "messages": [
    {
      "role": "user",
      "content": "I am going to Paris, what should I see?"
    },
    {
      "role": "assistant",
      "content": "Paris, the capital of France, is known for its stunning architecture, art museums, historical landmarks, and romantic atmosphere. Here are some of the top attractions to see in Paris:\n\n1. The Eiffel Tower: The iconic Eiffel Tower is one of the most recognizable landmarks in the world and offers breathtaking views of the city.\n2. The Louvre Museum: The Louvre is one of the world's largest and most famous museums, housing an impressive collection of art and artifacts, including the Mona Lisa.\n3. Notre-Dame Cathedral: This beautiful cathedral is one of the most famous landmarks in Paris and is known for its Gothic architecture and stunning stained glass windows.\n\nThese are just a few of the many attractions that Paris has to offer. With so much to see and do, it's no wonder that Paris is one of the most popular tourist destinations in the world."
    },
    {
      "role": "user",
      "content": "What is so great about #1?"
    }
  ],
  "max_tokens": 2048,
  "temperature": 0.8,
  "top_p": 0.1,
  "presence_penalty": 0,
  "frequency_penalty": 0
}
response = client.complete(payload)

print("Response:", response.choices[0].message.content)
print("Model:", response.model)
print("Usage:")
print("	Prompt tokens:", response.usage.prompt_tokens)
print("	Total tokens:", response.usage.total_tokens)
print("	Completion tokens:", response.usage.completion_tokens)