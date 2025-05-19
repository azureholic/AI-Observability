import os
import time
import random
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from azure.monitor.opentelemetry.exporter import AzureMonitorMetricExporter
from opentelemetry.metrics import set_meter_provider, get_meter

# load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

def setup_metrics(is_local=True):
    # Configure resource with service name
    resource = Resource(attributes={"service.name": "example-metrics-service"})

    if is_local:
        endpoint = os.getenv("LOCAL_OTEL_ENDPOINT")
        metric_exporter = OTLPMetricExporter(endpoint=f"{endpoint}/v1/metrics")
    else:
        connection_string = os.getenv("AZURE_MONITOR_CONNECTION_STRING")
        metric_exporter = AzureMonitorMetricExporter(connection_string=connection_string)
    
    # Create a metric reader that will collect metrics periodically
    reader = PeriodicExportingMetricReader(
        exporter=metric_exporter,
        export_interval_millis=10000  # Export metrics every 10 seconds
    )
    
    # Configure metrics with OTLP
    meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
    set_meter_provider(meter_provider)
    
    # Get a meter - a factory for creating instruments
    meter = get_meter("example-metrics")
    
    # Return the configured meter
    return meter

def main():
    # Set up metrics
    meter = setup_metrics(is_local=True)
    
    # Create instruments for different metric types
    
    # Counter - for incrementing values
    counter = meter.create_counter(
        name="requests_counter",
        description="Counts the number of requests",
        unit="1"
    )
    
    # Histogram - for measuring distributions of values
    histogram = meter.create_histogram(
        name="request_duration",
        description="Records the duration of requests",
        unit="ms"
    )
    
    # UpDownCounter - for values that can go up or down
    updown_counter = meter.create_up_down_counter(
        name="active_requests",
        description="Number of active requests",
        unit="1"
    )
    
    # Simulate some activity to generate metrics
    print("Generating metrics for 1 minute...")
    start_time = time.time()
    
    active_requests = 0
    
    while time.time() - start_time < 60:  # Run for 1 minute
        # Simulate a request
        counter.add(1, {"endpoint": "/api/data", "method": "GET"})
        
        # Simulate request duration
        duration = random.uniform(10, 500)  # Random duration between 10ms and 500ms
        histogram.record(duration, {"endpoint": "/api/data", "method": "GET"})
        
        # Simulate active requests
        new_requests = random.randint(1, 5)
        completed_requests = random.randint(0, active_requests) if active_requests > 0 else 0
        
        updown_counter.add(new_requests, {"status": "started"})
        active_requests += new_requests
        
        updown_counter.add(-completed_requests, {"status": "completed"})
        active_requests -= completed_requests
        
        print(f"Active requests: {active_requests}, Last request duration: {duration:.2f}ms")
        
        # Sleep for a random time to simulate intervals between requests
        time.sleep(random.uniform(0.5, 2.0))
    
    # Wait a bit longer to ensure metrics are exported
    print("Waiting for final metrics export...")
    time.sleep(15)
    print("Script execution completed.")

if __name__ == "__main__":
    main()
