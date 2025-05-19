import os, time
from azure.ai.projects import AIProjectClient
from azure.identity import AzureCliCredential
from azure.ai.inference.models import UserMessage
from opentelemetry import trace
from azure.monitor.opentelemetry import configure_azure_monitor
from dotenv import load_dotenv

load_dotenv()

project_client = AIProjectClient.from_connection_string(
    credential=AzureCliCredential(),
    conn_str=os.environ["AIFOUNDRY_PROJECT_CONNECTION_STRING"],
)

model_deployment_name = os.environ["AZURE_MAAS_CHAT_DEPLOYMENT_NAME"]

application_insights_connection_string = project_client.telemetry.get_connection_string()
configure_azure_monitor(connection_string=application_insights_connection_string)
project_client.telemetry.enable()

scenario = os.path.basename(__file__)
tracer = trace.get_tracer(__name__)

with tracer.start_as_current_span(scenario):
    
    inference_client = project_client.inference.get_chat_completions_client()

    response = inference_client.complete(
        model=model_deployment_name,
        messages=[UserMessage(content="How many feet are in a mile?")]
    )

print(response.choices[0].message.content)



