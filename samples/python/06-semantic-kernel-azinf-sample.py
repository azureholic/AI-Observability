import os
import asyncio
from dotenv import load_dotenv
from azure.identity import AzureCliCredential
from opentelemetry.sdk.resources import Resource
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry import trace
from azure.monitor.opentelemetry import configure_azure_monitor
from azure.ai.inference.tracing import AIInferenceInstrumentor 
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.azure_ai_inference import AzureAIInferenceChatCompletion
from azure.ai.inference.aio import ChatCompletionsClient

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))
connection_string = os.getenv("AZURE_MONITOR_CONNECTION_STRING")
azure_openai_endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
azure_openai_chat_deployment_name = os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT_NAME"]
resource = Resource.create({ResourceAttributes.SERVICE_NAME: "telemetry-ai-foundy"})

async def main():
    configure_azure_monitor(connection_string=connection_string)
    AIInferenceInstrumentor().instrument() 
    scenario = os.path.basename(__file__)
    tracer = trace.get_tracer(__name__)

    with tracer.start_as_current_span(scenario):
        kernel = Kernel()
        kernel.add_service(AzureAIInferenceChatCompletion(
            ai_model_id=azure_openai_chat_deployment_name,
            client=ChatCompletionsClient(
                endpoint=f"{str(azure_openai_endpoint).strip('/')}/openai/deployments/{azure_openai_chat_deployment_name}",
                credential=AzureCliCredential(),
                credential_scopes=["https://cognitiveservices.azure.com/.default"],
            ),
        ))
        
        answer = await kernel.invoke_prompt("How many feet are in a mile?", "generate_answer")
        print(answer)

if __name__ == "__main__":
    asyncio.run(main())
