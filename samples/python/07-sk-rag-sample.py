"""
Hotel RAG Demo using Semantic Kernel

This script demonstrates a Retrieval-Augmented Generation (RAG) application using:
- Azure AI Search for vector search on hotel data
- Azure OpenAI for embeddings and chat completion
- Semantic Kernel as the orchestration framework with plugin functionality

The application allows users to query hotel information in natural language
and returns relevant hotel recommendations based on the query.

Key enhancements:
- Vector search is presented as a KernelFunction that the LLM can decide when to call
- Chat history maintains previous search results for context
- OpenTelemetry instrumentation for observability

Requirements:
- Azure AI Search service with the 'hotels' index created
- Azure OpenAI service with text-embedding-ada-002 and a chat model deployed
- Environment variables set for all required services
"""

import os
import asyncio
from typing import List, Dict, Any
from dotenv import load_dotenv
from opentelemetry.sdk.resources import Resource
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry import trace
from opentelemetry.trace.span import Span
from setup_obversability import setup_observability

# Azure SDK packages
from azure.identity import AzureCliCredential, get_bearer_token_provider
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery

# Semantic Kernel imports
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.azure_ai_inference import (
    AzureAIInferenceChatCompletion, 
    AzureAIInferenceTextEmbedding,
    AzureAIInferenceChatPromptExecutionSettings
)
from semantic_kernel.contents.chat_history import ChatHistory
from azure.ai.inference.aio import ChatCompletionsClient, EmbeddingsClient
from semantic_kernel.functions import kernel_function

# Load environment variables
load_dotenv()

# Set up OpenTelemetry observability
resource = Resource.create({ResourceAttributes.SERVICE_NAME: "sk-rag-sample"})
connection_string = os.environ.get("AZURE_MONITOR_CONNECTION_STRING")
logger = setup_observability(connection_string, resource)

# Configuration - using environment variables
SEARCH_SERVICE_ENDPOINT = os.environ.get("AZURE_SEARCH_ENDPOINT")
SEARCH_INDEX_NAME = os.environ.get("AZURE_SEARCH_INDEX_NAME")
AZURE_OPENAI_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_EMBEDDING_DEPLOYMENT = os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME")
AZURE_OPENAI_CHAT_DEPLOYMENT = os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME")

# Set up authentication using Azure CLI
credential = AzureCliCredential()
token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")

# System prompt for the RAG application
SYSTEM_PROMPT = """
You are an AI assistant specializing in hotel recommendations. 

You have access to a searchHotels function that can search a database of hotels based on user queries.
You should decide if you need to call this function based on whether:
1. The user is asking about specific hotels or hotel features
2. The user's question requires up-to-date hotel information
3. You don't have sufficient context from previous searches to answer

If the user asks a question that doesn't require hotel information or if you already have 
relevant hotel information in the chat history, you can answer directly without searching.

When you do have hotel information, analyze the hotel details including name, location, 
description, amenities, and ratings to provide helpful recommendations.

For each recommended hotel, include:
1. The hotel name and location
2. A brief summary of why it matches the query
3. Key amenities that might be relevant to the query
4. Price per night and rating information

Your goal is to help the user find the perfect hotel based on their preferences.
"""

class HotelSearchPlugin:
    """Hotel Search Plugin for Semantic Kernel."""
    
    def __init__(self, search_client, embedding_service):
        self.search_client = search_client
        self.embedding_service = embedding_service
        self.tracer = trace.get_tracer(__name__)
    
    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embeddings for the user query."""
        embedding_result = await self.embedding_service.generate_embeddings([text])
        return embedding_result[0]
    
    @kernel_function(description="Search for hotels using natural language queries.")
    async def search_hotels(self, query: str, top_k: int = 3) -> str:
        """
        Search hotels using vector search based on the query.
        Returns formatted hotel information as a string.
        """
            
        # Generate embedding for the query
        query_embedding = await self.generate_embedding(query)
        vector_query = VectorizedQuery(
            vector=query_embedding,
            k_nearest_neighbors=top_k,
            fields="embedding"
        )
        
        # Perform the search
        search_results = self.search_client.search(
            search_text=None,  # Using vector search only, no text search
            vector_queries=[vector_query],
            select=["hotelId", "hotelName", "description", "location",
                    "rating", "pricePerNight", "amenities", "lastRenovationDate",
                    "roomCount", "parkingIncluded", "tags"],
            top=top_k
        )

        # Collect results
        hotels = []
        result_count = 0
        for result in search_results:
            hotels.append(dict(result))
            result_count += 1

        # Format hotel results for the LLM
        formatted_results = self.format_hotels_for_completion(hotels)
        return formatted_results
            
    
    def format_hotels_for_completion(self, hotels: List[Dict[str, Any]]) -> str:
        """Format hotel data for the chat completion prompt."""
        if not hotels:
            return "No hotels found matching the search criteria."
            
        hotel_info = []
        
        for i, hotel in enumerate(hotels, 1):
            # Convert amenities list to string
            amenities_str = ", ".join(hotel.get("amenities", []))
            
            # Format hotel information
            hotel_text = f"""
                        Hotel {i}:
                        Name: {hotel.get('hotelName', 'N/A')}
                        Location: {hotel.get('location', 'N/A')}
                        Description: {hotel.get('description', 'N/A')}
                        Rating: {hotel.get('rating', 'N/A')}/5.0
                        Price per night: ${hotel.get('pricePerNight', 'N/A')}
                        Amenities: {amenities_str}
                        Tags: {', '.join(hotel.get('tags', []))}
                        Room Count: {hotel.get('roomCount', 'N/A')}
                        Last Renovation: {hotel.get('lastRenovationDate', 'N/A')}
                        Parking Included: {'Yes' if hotel.get('parkingIncluded', False) else 'No'}
                        """
            hotel_info.append(hotel_text)
        
        return "\n".join(hotel_info)

class EnhancedHotelRagDemo:
    def __init__(self):
        """Initialize the Enhanced Hotel RAG Demo application."""
        self._setup_search_client()
        self._setup_kernel()
        self.chat_history = ChatHistory()
        self.chat_history.add_system_message(SYSTEM_PROMPT)
        
    def _setup_search_client(self):
        """Set up the Azure AI Search client."""
        if not SEARCH_SERVICE_ENDPOINT:
            raise ValueError("SEARCH_SERVICE_ENDPOINT environment variable not set")
        
        self.search_client = SearchClient(
            endpoint=SEARCH_SERVICE_ENDPOINT,
            index_name=SEARCH_INDEX_NAME,
            credential=credential
        )
    
    def _setup_kernel(self):
        """Set up Semantic Kernel with embeddings, chat completion services, and plugins."""
        if not AZURE_OPENAI_ENDPOINT:
            raise ValueError("AZURE_OPENAI_ENDPOINT environment variable not set")
        
        # Initialize the kernel
        self.kernel = Kernel()
        
        # Add text embedding service using AzureAIInferenceTextEmbedding
        self.embedding_service = AzureAIInferenceTextEmbedding(
            ai_model_id=AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
            service_id="text-embedding-service",
            client=EmbeddingsClient(
                endpoint=f"{str(AZURE_OPENAI_ENDPOINT).strip('/')}/openai/deployments/{AZURE_OPENAI_EMBEDDING_DEPLOYMENT}",
                credential=credential,
                credential_scopes=["https://cognitiveservices.azure.com/.default"],
            ),
        )
        self.kernel.add_service(self.embedding_service)
        
        # Add chat completion service using AzureAIInferenceChatCompletion
        self.chat_service = AzureAIInferenceChatCompletion(
            ai_model_id=AZURE_OPENAI_CHAT_DEPLOYMENT,
            service_id="chat-completion-service",
            client=ChatCompletionsClient(
                endpoint=f"{str(AZURE_OPENAI_ENDPOINT).strip('/')}/openai/deployments/{AZURE_OPENAI_CHAT_DEPLOYMENT}",
                credential=credential,
                credential_scopes=["https://cognitiveservices.azure.com/.default"],
            ),
        )
        self.kernel.add_service(self.chat_service)
        
        # Create and register the hotel search plugin
        self._register_hotel_search_plugin()
    
    def _register_hotel_search_plugin(self):
        """Register the hotel search plugin with the kernel."""
        
        # Create the plugin instance
        hotel_plugin = HotelSearchPlugin(self.search_client, self.embedding_service)
        # Register the plugin with the kernel
        self.kernel.add_plugin(plugin=hotel_plugin)

        
    
    async def process_query(self, query: str) -> str:
        """Process a user query end-to-end using function calling approach."""
        # tracer = trace.get_tracer(__name__)

        # with tracer.start_as_current_span("process_query"):
        #     # Add user query to chat history
        self.chat_history.add_user_message(query)
        
        # Create execution settings with function calling enabled
        execution_settings = AzureAIInferenceChatPromptExecutionSettings(
            max_tokens=2000,
            temperature=0.0,
            function_choice_behavior="auto"  # Let the model decide when to call tools
        )
        
        # Generate response with potential function calling
        result = await self.chat_service.get_chat_message_content(
            chat_history=self.chat_history,
            settings=execution_settings,
            kernel=self.kernel
        )


        
        # Add AI response to chat history for context in future queries
        self.chat_history.add_assistant_message(result.content)
        
        return result

async def main():
    """Main function to run the RAG demo."""
    scenario = os.path.basename(__file__)
    tracer = trace.get_tracer(__name__)

    with tracer.start_as_current_span(scenario):
        try:
                # Initialize the demo
            rag_demo = EnhancedHotelRagDemo()
            
            print("Welcome to the Enhanced Hotel RAG Demo!")
            print("Ask questions about hotels, or type EXIT to quit.\n")
            
            while True:
                # Get user input
                user_input = input("\nYour question: ")
                
                # Check for exit command
                if user_input.strip().upper() == "EXIT":
                    print("Thank you for using the Hotel RAG Demo. Goodbye!")
                    break


                # Process the query
                print("\nProcessing your question...")
                response = await rag_demo.process_query(user_input)
                
                # Display the response
                print("\n" + "="*80)
                print("AI Response:")
                print("="*80)
                print(response)
                print("="*80)
        
        except Exception as e:
            print(f"Error: {str(e)}")
            import traceback
            print(traceback.format_exc())

if __name__ == "__main__":
    asyncio.run(main())
