import os
import time
import random
import logging
import sys
import json
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter
from opentelemetry.trace.status import Status, StatusCode
from opentelemetry.sdk.trace.sampling import ALWAYS_ON
from opentelemetry.trace import SpanKind
from opentelemetry.context import context as context_api

# load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

class Problem:
    """
    Represents an error condition based on RFC 7807 HTTP Problem Details.
    Used instead of exceptions for more structured error handling and observability.
    """
    def __init__(self, type, title, status=None, detail=None, instance=None, **extras):
        self.type = type          # URI reference that identifies the problem type
        self.title = title        # Short human-readable summary
        self.status = status      # HTTP status code
        self.detail = detail      # Human-readable explanation
        self.instance = instance  # URI reference that identifies this specific occurrence
        self.extras = extras      # Additional properties specific to the problem
        
    def __str__(self):
        return f"{self.title}: {self.detail or ''}"
    
    def to_dict(self):
        """Convert to dictionary for serialization"""
        result = {
            "type": self.type,
            "title": self.title
        }
        if self.status is not None:
            result["status"] = self.status
        if self.detail is not None:
            result["detail"] = self.detail
        if self.instance is not None:
            result["instance"] = self.instance
        result.update(self.extras)
        return result
    
    def to_json(self):
        """Convert to JSON string"""
        return json.dumps(self.to_dict())

# Legacy exception for backward compatibility
class CacheException(Exception):
    """Exception raised when the cache service is unavailable."""
    pass

def setup_tracing(is_local=True):
    """Set up OpenTelemetry tracing"""
    # Configure resource with service name and other required attributes
    resource = Resource(attributes={
        "service.name": "example-tracing-service",
        "service.namespace": "demo",
        "service.instance.id": "instance-1",
        "telemetry.sdk.name": "opentelemetry",
        "telemetry.sdk.language": "python",
        "telemetry.sdk.version": "1.11.0",
        "ai.cloud.role": "tracing-demo-app",  # Legacy Application Insights attribute
        "ai.cloud.roleInstance": "instance-1"  # Legacy Application Insights attribute
    })

    # Create a tracer provider
    tracer_provider = TracerProvider(resource=resource, sampler=ALWAYS_ON)
    trace.set_tracer_provider(tracer_provider)

    # Configure the exporter
    if is_local:
        endpoint = os.getenv("LOCAL_OTEL_ENDPOINT")
        otlp_exporter = OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces")
    else:
        connection_string = os.getenv("AZURE_MONITOR_CONNECTION_STRING")
        otlp_exporter = AzureMonitorTraceExporter(connection_string=connection_string)
    
    # Add the exporter to the tracer provider
    span_processor = BatchSpanProcessor(otlp_exporter)
    tracer_provider.add_span_processor(span_processor)
    
    # Set up logging for trace context
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter("[TRACE] %(asctime)s - %(message)s"))
    logger = logging.getLogger("tracing-example")
    logger.setLevel(logging.INFO)
    logger.addHandler(console_handler)
    
    # Return the tracer and logger
    return trace.get_tracer("example-tracer"), logger

def cache_lookup(tracer, key):
    """
    Simulate a cache lookup operation using Problem pattern instead of exceptions
    Returns either the value, None (for miss), or a Problem object (for error)
    """
    # Add a peer.service attribute for dependency tracking in Azure Monitor
    attributes = {
        "db.system": "redis",
        "db.operation": "GET",
        "db.statement": f"GET {key}",
        "net.peer.name": "redis.example.com",
        "net.peer.port": 6379,
        "cache.key": key,
        "peer.service": "redis-cache",  # Important for Azure Monitor dependency tracking
        "component": "redis",  # Legacy Application Insights attribute
        "messaging.system": "redis",  # Additional attribute to help with dependency categorization
        "rpc.system": "redis"  # Additional attribute to help with dependency categorization
    }
    
    # Use explicit span context propagation to ensure parent-child relationship
    with tracer.start_as_current_span(
        name="Redis GET", 
        kind=trace.SpanKind.CLIENT,
        attributes=attributes
    ) as span:
        # Simulate some processing time
        time.sleep(0.1)
        
        # For demonstration, we'll use a fixed cache state
        cache_data = {"product-1001": "Laptop", "product-2002": "Smartphone"}
        
        if key in cache_data:
            span.set_attribute("cache.hit", True)
            return cache_data[key]
        else:
            span.set_attribute("cache.hit", False)
            return None

def database_query(tracer, key):
    """
    Simulate a database query operation, possibly returning a Problem
    """
    # Add a peer.service attribute for dependency tracking in Azure Monitor
    attributes = {
        "db.system": "postgresql",
        "db.name": "products",
        "db.operation": "SELECT",
        "db.statement": f"SELECT * FROM products WHERE id = '{key}'",
        "net.peer.name": "database.example.com",
        "net.peer.port": 5432,
        "db.key": key,
        "peer.service": "postgres-db",  # Important for Azure Monitor dependency tracking
        "component": "postgresql",  # Legacy Application Insights attribute
        "messaging.system": "postgresql",  # Additional attribute to help with dependency categorization
        "rpc.system": "postgresql"  # Additional attribute to help with dependency categorization
    }
    
    # Use explicit span context propagation to ensure parent-child relationship
    with tracer.start_as_current_span(
        name="PostgreSQL Query", 
        kind=trace.SpanKind.CLIENT,
        attributes=attributes
    ) as span:
        
        # Simulate database processing time
        time.sleep(0.3)
        
        # Mock database data
        db_data = {
            "product-1001": "Laptop",
            "product-2002": "Smartphone",
            "product-3003": "Tablet",
            "product-4004": "Desktop Computer"
        }
        
        # Rarely (1% chance) simulate DB failure
        if random.random() < 0.01:
            problem = Problem(
                type="https://example.com/problems/database-error",
                title="Database Error",
                status=500,
                detail="The database is experiencing technical difficulties",
                instance=f"/database/query/{key}"
            )
            
            # Record problem in span
            span.set_status(Status(StatusCode.ERROR))
            span.set_attribute("error", True)
            span.set_attribute("error.type", "DatabaseError")
            span.set_attribute("error.message", str(problem))
            span.set_attribute("problem.type", problem.type)
            span.set_attribute("problem.title", problem.title)
            
            return problem
        
        if key in db_data:
            span.set_attribute("db.found", True)
            return db_data[key]
        else:
            span.set_attribute("db.found", False)
            # Return a "not found" problem rather than null
            return Problem(
                type="https://example.com/problems/product-not-found",
                title="Product Not Found",
                status=404,
                detail=f"Product with ID {key} was not found in the database",
                instance=f"/products/{key}"
            )

def cache_update(tracer, key, value):
    """Simulate updating the cache with new data, possibly returning a Problem"""
    # Add a peer.service attribute for dependency tracking in Azure Monitor
    attributes = {
        "db.system": "redis",
        "db.operation": "SET",
        "db.statement": f"SET {key} {value}",
        "net.peer.name": "redis.example.com",
        "net.peer.port": 6379,
        "cache.key": key,
        "cache.value": value,
        "peer.service": "redis-cache",  # Important for Azure Monitor dependency tracking
        "component": "redis",  # Legacy Application Insights attribute
        "messaging.system": "redis",  # Additional attribute to help with dependency categorization
        "rpc.system": "redis"  # Additional attribute to help with dependency categorization
    }
    
    # Use explicit span context propagation to ensure parent-child relationship
    with tracer.start_as_current_span(
        name="Redis SET", 
        kind=trace.SpanKind.CLIENT,
        attributes=attributes
    ) as span:
        
        # Simulate cache update time
        time.sleep(0.1)
        
        # Rarely (5% chance) simulate update failure
        if random.random() < 0.05:
            problem = Problem(
                type="https://example.com/problems/cache-update-failed",
                title="Cache Update Failed",
                status=500,
                detail="Unable to update cache with new value",
                instance=f"/cache/{key}"
            )
            
            # Record problem in span
            span.set_status(Status(StatusCode.ERROR))
            span.set_attribute("error", True)
            span.set_attribute("error.type", "CacheUpdateFailed")
            span.set_attribute("error.message", str(problem))
            
            return problem
        
        return True

def product_lookup(tracer, logger, product_id, scenario=None):
    """Main product lookup function that orchestrates the entire process"""
    # Create a unique trace ID for this request
    trace_id = f"scenario-{scenario}-{random.randint(1000000, 9999999)}"
    
    # Ensure proper categorization in Azure Monitor as a Request
    attributes = {
        "http.method": "GET",
        "http.url": f"https://example.com/api/products/{product_id}",
        "http.scheme": "https",
        "http.host": "example.com",
        "http.target": f"/api/products/{product_id}",
        "http.route": "/api/products/{id}",
        "http.status_code": 200,
        "product.id": product_id,
        "scenario": scenario,
        # For improved Azure Monitor correlation
        "operation.name": f"GET /api/products/{{{product_id}}}",
        # For legacy Application Insights correlation
        "operation.id": trace_id,
        "component": "api"
    }
    
    # For Azure Monitor, use these specific attribute names to ensure proper request classification
    with tracer.start_as_current_span(
        name=f"GET Product {product_id}",
        kind=trace.SpanKind.SERVER,
        attributes=attributes
    ) as span:
        logger.info(f"Starting product lookup for {product_id} - Scenario {scenario}")
        
        # Attempt to get data from cache
        cache_result = cache_lookup(tracer, product_id)
        
        # Check if we got a Problem instead of a value
        if isinstance(cache_result, Problem):
            logger.error(f"Cache error: {cache_result}")
            # Update span with problem details
            span.set_attribute("problem.detected", "cache")
            span.set_attribute("problem.title", cache_result.title)
            # No exception is thrown - we continue with the database lookup
        elif cache_result:
            logger.info(f"Cache hit for {product_id}: {cache_result}")
            span.set_attribute("lookup.source", "cache")
            span.set_attribute("http.status_code", 200)
            return cache_result
        else:
            logger.info(f"Cache miss for {product_id}")
        
        # If not in cache or cache failed, query the database
        db_result = database_query(tracer, product_id)
        
        # Check if we got a Problem from database
        if isinstance(db_result, Problem):
            logger.error(f"Database error: {db_result}")
            # Update main span with problem details and status code
            span.set_attribute("problem.detected", "database")
            span.set_attribute("problem.title", db_result.title)
            span.set_attribute("http.status_code", db_result.status)
            
            if db_result.status >= 500:
                span.set_status(Status(StatusCode.ERROR))
            
            return db_result
        
        # If we got a value from the database
        logger.info(f"Database hit for {product_id}: {db_result}")
        span.set_attribute("lookup.source", "database")
        
        # Try to update cache if it wasn't an error (just a miss)
        if not isinstance(cache_result, Problem):
            cache_update_result = cache_update(tracer, product_id, db_result)
            
            if isinstance(cache_update_result, Problem):
                logger.error(f"Failed to update cache: {cache_update_result}")
                span.set_attribute("cache.update.failed", True)
            else:
                logger.info(f"Cache updated with {product_id}: {db_result}")
                span.set_attribute("cache.update.success", True)
        
        return db_result

def main():
    # Set up tracing
    tracer, logger = setup_tracing(is_local=True)
    
    logger.info("Starting trace demonstration with 3 distinct scenarios...")
    
    # Run scenarios in separate traces with better isolation
    run_scenario_1(tracer, logger)
    
    # Wait a bit before starting the next scenario to ensure complete separation
    time.sleep(2)
    
    run_scenario_2(tracer, logger)
    
    # Wait a bit before starting the next scenario to ensure complete separation
    time.sleep(2)
    
    run_scenario_3(tracer, logger)
    
    logger.info("Trace demonstration completed. All 3 scenarios executed.")
    
    # Wait longer to ensure all telemetry is flushed
    logger.info("Waiting for all telemetry to be exported...")
    time.sleep(10)

def run_scenario_1(tracer, logger):
    """Scenario 1: Cache miss, database hit, cache update"""
    logger.info("=== Scenario 1: Cache miss, database hit, cache update ===")
    
    # Create a new trace context for each scenario
    # This ensures each scenario shows up as a separate request in Azure Monitor
    ctx = trace.set_span_in_context(trace.INVALID_SPAN)
    token = trace.context_api.attach(ctx)
    
    try:
        # Use a product ID that won't be in the initial cache
        result = product_lookup(tracer, logger, "product-3003", "scenario_1")
        logger.info(f"Scenario 1 result: {result}")
    finally:
        # Clean up the context
        trace.context_api.detach(token)

def run_scenario_2(tracer, logger):
    """Scenario 2: Cache hit, no database query needed"""
    logger.info("\n=== Scenario 2: Cache hit, no database query needed ===")
    
    # Create a new trace context for each scenario
    # This ensures each scenario shows up as a separate request in Azure Monitor
    ctx = trace.set_span_in_context(trace.INVALID_SPAN)
    token = trace.context_api.attach(ctx)
    
    try:
        # Use a product ID that should be in the cache
        result = product_lookup(tracer, logger, "product-1001", "scenario_2")
        logger.info(f"Scenario 2 result: {result}")
    finally:
        # Clean up the context
        trace.context_api.detach(token)

def run_scenario_3(tracer, logger):
    """Scenario 3: Cache unavailable, fallback to database"""
    logger.info("\n=== Scenario 3: Cache unavailable, fallback to database ===")
    
    # Create a new trace context for each scenario
    # This ensures each scenario shows up as a separate request in Azure Monitor
    ctx = trace.set_span_in_context(trace.INVALID_SPAN)
    token = trace.context_api.attach(ctx)
    
    try:
        # Monkey patch the cache_lookup function to simulate unavailability
        original_cache_lookup = cache_lookup
        
        def unavailable_cache(tracer, key):
            # Add a peer.service attribute for dependency tracking in Azure Monitor
            attributes = {
                "db.system": "redis",
                "db.operation": "GET",
                "db.statement": f"GET {key}",
                "net.peer.name": "redis.example.com",
                "net.peer.port": 6379,
                "cache.key": key,
                "peer.service": "redis-cache",  # Important for Azure Monitor dependency tracking
                "component": "redis",  # Legacy Application Insights attribute
                "messaging.system": "redis",  # Additional attribute to help with dependency categorization
                "rpc.system": "redis"  # Additional attribute to help with dependency categorization
            }
            
            with tracer.start_as_current_span(
                name="Redis GET", 
                kind=trace.SpanKind.CLIENT,
                attributes=attributes
            ) as span:
                # Always return a Problem instead of throwing an exception
                problem = Problem(
                    type="https://example.com/problems/cache-unavailable",
                    title="Cache Service Unavailable",
                    status=503,
                    detail="The cache service is currently unavailable",
                    instance=f"/cache/{key}",
                    retry_after=120
                )
                
                # Record problem in span
                span.set_status(Status(StatusCode.ERROR))
                span.set_attribute("error", True)
                span.set_attribute("error.type", "CacheUnavailable")
                span.set_attribute("error.message", str(problem))
                span.set_attribute("problem.type", problem.type)
                span.set_attribute("problem.title", problem.title)
                span.set_attribute("problem.status", problem.status)
                
                # Simulate some processing time to ensure consistent span timing
                time.sleep(0.1)
                
                # Return the problem instead of throwing an exception
                return problem
        
        # Replace cache_lookup temporarily
        globals()['cache_lookup'] = unavailable_cache
        
        # Run the scenario
        result = product_lookup(tracer, logger, "product-4004", "scenario_3")
        logger.info(f"Scenario 3 result: {result}")
        
        # Restore original function
        globals()['cache_lookup'] = original_cache_lookup
    finally:
        # Clean up the context
        trace.context_api.detach(token)

if __name__ == "__main__":
    main()
    # Keep the application running briefly to allow the batch processors to export
    import time
    time.sleep(20)  # Wait for 20 seconds to ensure traces are exported
    print("Script execution completed.")
