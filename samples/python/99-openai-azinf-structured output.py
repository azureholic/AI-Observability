import os
import json
from pydantic import BaseModel, ConfigDict, Field
from typing import List
    
from azure.ai.projects import AIProjectClient
from azure.identity import AzureCliCredential
from azure.ai.inference.models import UserMessage, SystemMessage, JsonSchemaFormat
from opentelemetry import trace
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry.instrumentation.openai_v2 import OpenAIInstrumentor
from dotenv import load_dotenv


load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

project_client = AIProjectClient.from_connection_string(
    credential=AzureCliCredential(),
    conn_str=os.environ["AIFOUNDRY_PROJECT_CONNECTION_STRING"],
)

model_deployment_name = os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT_NAME"]
application_insights_connection_string = project_client.telemetry.get_connection_string()

configure_azure_monitor(connection_string=application_insights_connection_string)
project_client.telemetry.enable()
OpenAIInstrumentor().instrument()

scenario = os.path.basename(__file__)
tracer = trace.get_tracer(__name__)

 # These classes define the structure of a cooking recipe.
# For more information, see https://docs.pydantic.dev/latest/concepts/json_schema/
class CookingIngredient(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    quantity: str

class CookingStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    step: int
    directions: str

class CookingRecipe(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    servings: int
    prep_time: int = Field(
        description="Preperation time in minutes",
    )
    cooking_time: int = Field(
        description="Cooking time in minutes",
    )
    ingredients: List[CookingIngredient]
    steps: List[CookingStep]
    notes: str


with tracer.start_as_current_span(scenario):
    inference_client = project_client.inference.get_azure_openai_client(api_version="2025-04-01-preview")

    response = inference_client.beta.chat.completions.parse(
        model=model_deployment_name,
        response_format=CookingRecipe,
        messages=[
            SystemMessage("You are a helpful assistant."),
            UserMessage("Please give me directions and ingredients to bake a chocolate cake."),
        ],
    )

    print(response.choices[0].message.content)

    
