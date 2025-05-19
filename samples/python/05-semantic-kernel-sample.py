import os
import asyncio
from dotenv import load_dotenv
from azure.identity import AzureCliCredential, get_bearer_token_provider
from opentelemetry.sdk.resources import Resource
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace.sampling import ALWAYS_ON
from opentelemetry.instrumentation.openai import OpenAIInstrumentor
from azure.monitor.opentelemetry import configure_azure_monitor


from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))
azure_openai_endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
azure_openai_chat_deployment_name = os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT_NAME"]

token_provider = get_bearer_token_provider(AzureCliCredential(), "https://cognitiveservices.azure.com/.default")
resource = Resource.create({ResourceAttributes.SERVICE_NAME: "semantic-kernel-aoai"})
connection_string=os.environ["AZURE_MONITOR_CONNECTION_STRING"]

def set_up_otel(is_local=True):
      if is_local:
        endpoint = os.getenv("LOCAL_OTEL_ENDPOINT")
        # Create a tracer provider
        tracer_provider = TracerProvider(resource=resource, sampler=ALWAYS_ON)
        trace.set_tracer_provider(tracer_provider)
        otlp_exporter = OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces")
        span_processor = BatchSpanProcessor(otlp_exporter)
        tracer_provider.add_span_processor(span_processor)
        OpenAIInstrumentor().instrument()

      else:
        connection_string = os.getenv("AZURE_MONITOR_CONNECTION_STRING")
        configure_azure_monitor(connection_string)
        OpenAIInstrumentor().instrument()

async def main():
    set_up_otel(is_local=True)
    
    kernel = Kernel()
    kernel.add_service(AzureChatCompletion(
            endpoint=azure_openai_endpoint,
            deployment_name=azure_openai_chat_deployment_name,
            ad_token_provider=token_provider
        ))

    scenario = os.path.basename(__file__)
    tracer = trace.get_tracer(__name__)


    with tracer.start_as_current_span(scenario):
        
        answer = await kernel.invoke_prompt("How many feet are in a mile?")

    print(answer)

if __name__ == "__main__":
    asyncio.run(main())
