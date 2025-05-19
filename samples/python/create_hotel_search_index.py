"""
Hotel Search Index Setup Script

This script creates an Azure AI Search index with bogus hotel data and embeddings for vector search.
It uses Azure OpenAI's text-embedding-ada-002 model to generate embeddings for vector search.
Authentication is handled using DefaultAzureCredential.

Requirements:
- Azure AI Search service
- Azure OpenAI service with text-embedding-ada-002 model deployed
"""

import os
import json
import time
import random
from typing import List, Dict, Any
import uuid
from dotenv import load_dotenv

# Azure SDK packages
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchField,
    SearchFieldDataType,
    SimpleField,
    SearchableField,
    VectorSearch,
    VectorSearchProfile,
    HnswAlgorithmConfiguration,
    VectorSearchAlgorithmKind,
    VectorSearchAlgorithmMetric,
)

from openai import AzureOpenAI
load_dotenv()
# Configuration - In production, these should come from environment variables or Key Vault
SEARCH_SERVICE_ENDPOINT = os.environ.get("SEARCH_SERVICE_ENDPOINT")
SEARCH_INDEX_NAME = "hotels"

AZURE_OPENAI_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT") 
AZURE_OPENAI_DEPLOYMENT = os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-ada-002")


token_provider = get_bearer_token_provider(DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default")


# Hotel data generation
HOTEL_LOCATIONS = [
    "New York, NY", "Los Angeles, CA", "Chicago, IL", "Miami, FL",
    "San Francisco, CA", "Las Vegas, NV", "Seattle, WA", "Boston, MA",
    "Washington, DC", "Denver, CO", "Austin, TX", "New Orleans, LA",
    "San Diego, CA", "Portland, OR", "Nashville, TN", "Phoenix, AZ"
]

HOTEL_NAME_PREFIXES = ["Grand", "Royal", "Luxury", "Elite", "Premium", "Majestic", "Sunset", "Ocean", 
                       "Downtown", "Riverside", "Metropolitan", "Superior", "Heritage", "Coastal", "Urban", "Skyline"]

HOTEL_NAME_SUFFIXES = ["Hotel", "Resort", "Suites", "Inn", "Lodge", "Plaza", "Palace", "Residence", 
                       "Retreat", "Mansion", "Castle", "Villa", "Haven", "Towers", "Club", "Grand Hotel"]

HOTEL_AMENITIES = [
    "Free Wi-Fi", "Swimming Pool", "Fitness Center", "Spa", "Restaurant", 
    "Bar/Lounge", "Room Service", "Business Center", "Airport Shuttle", 
    "Concierge Service", "Pet Friendly", "Valet Parking", "EV Charging", 
    "Conference Rooms", "Rooftop Pool", "Private Beach", "Tennis Courts",
    "Kids Club", "Golf Course", "Water Park", "Casino", "Yoga Classes"
]

def create_search_index(index_client: SearchIndexClient, index_name: str) -> None:
    """Create the search index with vector capabilities."""
    
    # Define fields for the index
    fields = [
        SimpleField(name="hotelId", type=SearchFieldDataType.String, key=True, sortable=True),
        SearchableField(name="hotelName", type=SearchFieldDataType.String, sortable=True),
        SearchableField(name="description", type=SearchFieldDataType.String),
        SearchableField(name="location", type=SearchFieldDataType.String, sortable=True, filterable=True),
        SimpleField(name="rating", type=SearchFieldDataType.Double, sortable=True, filterable=True),
        SimpleField(name="pricePerNight", type=SearchFieldDataType.Double, sortable=True, filterable=True),
        SimpleField(name="amenities", type=SearchFieldDataType.Collection(SearchFieldDataType.String), filterable=True),
        SimpleField(name="lastRenovationDate", type=SearchFieldDataType.DateTimeOffset, sortable=True, filterable=True),
        SimpleField(name="roomCount", type=SearchFieldDataType.Int32, sortable=True, filterable=True),
        SimpleField(name="checkInTime", type=SearchFieldDataType.String),
        SimpleField(name="checkOutTime", type=SearchFieldDataType.String),
        SimpleField(name="parkingIncluded", type=SearchFieldDataType.Boolean, filterable=True),
        SimpleField(name="tags", type=SearchFieldDataType.Collection(SearchFieldDataType.String), filterable=True),
        # Vector field for embedding
        SearchField(
            name="embedding",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            vector_search_dimensions=1536,  # Dimension for text-embedding-ada-002
            vector_search_profile_name="vectorConfig"
        )
    ]

    # Define vector search config
    vector_search = VectorSearch(
        profiles=[
            VectorSearchProfile(
                name="vectorConfig",
                algorithm_configuration_name="vectorAlgorithmConfig"
            )
        ],
        algorithms=[
            HnswAlgorithmConfiguration(
                name="vectorAlgorithmConfig",
                kind=VectorSearchAlgorithmKind.HNSW,
                parameters={
                    "m": 4,
                    "efConstruction": 400,
                    "efSearch": 500,
                    "metric": VectorSearchAlgorithmMetric.COSINE
                }
            )
        ]
    )

    # Create the index
    index = SearchIndex(name=index_name, fields=fields, vector_search=vector_search)
    result = index_client.create_or_update_index(index)
    print(f"Index {result.name} created or updated")
    
    # Small delay to ensure index is ready
    time.sleep(5)
    return result

def generate_random_hotel() -> Dict[str, Any]:
    """Generate random hotel data."""
    location = random.choice(HOTEL_LOCATIONS)
    name_prefix = random.choice(HOTEL_NAME_PREFIXES)
    name_suffix = random.choice(HOTEL_NAME_SUFFIXES)
    hotel_name = f"{name_prefix} {location.split(',')[0]} {name_suffix}"
    
    # Select 5-10 random amenities
    num_amenities = random.randint(5, 15)
    amenities = random.sample(HOTEL_AMENITIES, num_amenities)
    
    # Generate tags
    tags = []
    if "Pet Friendly" in amenities:
        tags.append("pet-friendly")
    if "Swimming Pool" in amenities:
        tags.append("pool")
    if "Fitness Center" in amenities:
        tags.append("fitness")
    if any(spa in amenities for spa in ["Spa"]):
        tags.append("spa")
    if "Restaurant" in amenities:
        tags.append("dining")
    if "Business Center" in amenities or "Conference Rooms" in amenities:
        tags.append("business")
    if "Kids Club" in amenities or "Water Park" in amenities:
        tags.append("family-friendly")
    if "Casino" in amenities:
        tags.append("entertainment")
    if "EV Charging" in amenities:
        tags.append("eco-friendly")
    
    # Generate description based on amenities and location
    description_parts = [
        f"Welcome to {hotel_name}, a premier destination in the heart of {location}.",
        f"Our {random.choice(['elegant', 'luxurious', 'comfortable', 'modern', 'charming'])} hotel offers"
    ]
    
    if "Swimming Pool" in amenities:
        pool_type = random.choice(["outdoor", "indoor", "rooftop", "infinity"])
        description_parts.append(f"a stunning {pool_type} swimming pool")
    
    if "Restaurant" in amenities:
        cuisine = random.choice(["international", "local", "gourmet", "fusion", "award-winning"])
        description_parts.append(f"an {cuisine} restaurant")
    
    if "Fitness Center" in amenities:
        description_parts.append("a state-of-the-art fitness center")
    
    if "Spa" in amenities:
        description_parts.append("a relaxing spa facility")
    
    description_parts.append(f"Located just {random.randint(1, 15)} minutes from {random.choice(['downtown', 'the airport', 'major attractions', 'the beach', 'shopping centers'])}")
    description_parts.append("our hotel provides the perfect base for both business and leisure travelers.")
    
    description = " ".join(description_parts)
    
    # Generate remaining data
    hotel = {
        "hotelId": str(uuid.uuid4()),
        "hotelName": hotel_name,
        "description": description,
        "location": location,
        "rating": round(random.uniform(3.0, 5.0), 1),  # Rating between 3.0 and 5.0
        "pricePerNight": round(random.uniform(100, 1000), 2),  # Price between $100 and $1000
        "amenities": amenities,
        "lastRenovationDate": f"2020-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}T00:00:00Z",
        "roomCount": random.randint(50, 500),
        "checkInTime": f"{random.randint(12, 16):02d}:00",
        "checkOutTime": f"{random.randint(9, 12):02d}:00",
        "parkingIncluded": random.choice([True, False]),
        "tags": tags
    }
    
    return hotel

def generate_embeddings(openai_client: AzureOpenAI, hotels: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Generate embeddings for hotel descriptions using Azure OpenAI."""
    hotels_with_embeddings = []
    
    for hotel in hotels:
        text_to_embed = f"{hotel['hotelName']} - {hotel['description']} - {hotel['location']}"
        
        # Generate embeddings
        embedding_response = openai_client.embeddings.create(
            input=text_to_embed,
            model=AZURE_OPENAI_DEPLOYMENT,
        )
        
        # Add embedding to hotel data
        hotel["embedding"] = embedding_response.data[0].embedding
        hotels_with_embeddings.append(hotel)
        
        # Small delay to respect rate limits
        time.sleep(0.5)
        
    return hotels_with_embeddings

def main():
    """Main function to create search index and upload hotel data."""
    try:
        # Check environment variables
        if not SEARCH_SERVICE_ENDPOINT:
            raise ValueError("SEARCH_SERVICE_ENDPOINT environment variable not set")
        if not AZURE_OPENAI_ENDPOINT:
            raise ValueError("AZURE_OPENAI_ENDPOINT environment variable not set")
        
        # Set up authentication using DefaultAzureCredential
        credential = DefaultAzureCredential()
        
        # Create Azure AI Search index client
        search_index_client = SearchIndexClient(
            endpoint=SEARCH_SERVICE_ENDPOINT,
            credential=credential,
        )
        
        # Create the index
        print(f"Creating search index '{SEARCH_INDEX_NAME}'...")
        create_search_index(search_index_client, SEARCH_INDEX_NAME)
        
        # Set up search client for the index
        search_client = SearchClient(
            endpoint=SEARCH_SERVICE_ENDPOINT,
            index_name=SEARCH_INDEX_NAME,
            credential=credential,
        )
        
        # Set up Azure OpenAI client for embeddings
        openai_client = AzureOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            azure_deployment=AZURE_OPENAI_DEPLOYMENT,
            azure_ad_token_provider=token_provider,
            api_version="2024-02-15-preview"
        )
        
        # Generate hotel data
        print("Generating random hotel data...")
        hotels = [generate_random_hotel() for _ in range(16)]
        
        # Generate embeddings for hotels
        print("Generating embeddings for hotel descriptions...")
        hotels_with_embeddings = generate_embeddings(openai_client, hotels)
        
        # Check for existing hotels and filter them out
        print("Checking for existing hotels in the index...")
        existing_hotel_ids = set()
        
        try:
            # Get all documents from the index with a wildcard search
            search_results = search_client.search(search_text="*", include_total_count=True)
            for result in search_results:
                existing_hotel_ids.add(result["hotelId"])
            
            print(f"Found {len(existing_hotel_ids)} existing hotel(s) in the index.")
        except Exception as e:
            print(f"Warning: Error checking existing hotels: {str(e)}")
            print("Continuing with upload...")
        
        # Filter out existing hotels
        new_hotels = [hotel for hotel in hotels_with_embeddings if hotel["hotelId"] not in existing_hotel_ids]
        print(f"Uploading {len(new_hotels)} new hotels to the index...")
        
        if not new_hotels:
            print("No new hotels to upload.")
            uploaded_count = 0
            failed_count = 0
        else:
            # Upload in batches to handle large datasets more efficiently
            batch_size = 50
            uploaded_count = 0
            failed_count = 0
            
            for i in range(0, len(new_hotels), batch_size):
                batch = new_hotels[i:i + batch_size]
                try:
                    result = search_client.upload_documents(documents=batch)
                    # In Azure Search SDK, results are a list of IndexingResults
                    for doc_result in result:
                        if doc_result.succeeded:
                            uploaded_count += 1
                        else:
                            failed_count += 1
                    print(f"Batch {i//batch_size + 1}: Processed {len(batch)} documents.")
                except Exception as e:
                    print(f"Error uploading batch {i//batch_size + 1}: {str(e)}")
                    failed_count += len(batch)
        
        # Print results
        print(f"Uploaded {uploaded_count} hotel documents to the search index")
        print(f"Failed to upload {failed_count} hotel documents")
        
        # Print sample hotel for verification
        print("\nSample hotel data:")
        print(json.dumps(hotels[0], indent=2, default=str))
        
        print("\nSuccessfully created search index and uploaded hotels with vector embeddings.")
        
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        print(traceback.format_exc())

if __name__ == "__main__":
    main()
