import os
import asyncio
import logging
from dotenv import load_dotenv
from azure.identity import AzureCliCredential, get_bearer_token_provider
from opentelemetry._logs import set_logger_provider
from opentelemetry.metrics import set_meter_provider
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.metrics.view import DropAggregation, View
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.trace import set_tracer_provider
from opentelemetry import trace
from opentelemetry.trace.span import Span
from opentelemetry.trace import set_span_in_context
from azure.monitor.opentelemetry import configure_azure_monitor
from azure.ai.inference.tracing import AIInferenceInstrumentor 


from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from semantic_kernel.connectors.ai.azure_ai_inference import AzureAIInferenceChatCompletion
from azure.ai.inference.aio import ChatCompletionsClient


from azure.monitor.opentelemetry.exporter import (
    AzureMonitorLogExporter,
    AzureMonitorMetricExporter,
    AzureMonitorTraceExporter,
)

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
