import os
import logging
import sys
from opentelemetry.sdk.resources import Resource
from opentelemetry._logs import set_logger_provider
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from azure.monitor.opentelemetry.exporter import AzureMonitorLogExporter

# load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

def setup_logging(is_local=True):
    # Configure resource with service name
    resource = Resource(attributes={"service.name": "example-logging-service"})

    if is_local:
        endpoint = os.getenv("LOCAL_OTEL_ENDPOINT")
        otlp_log_exporter = OTLPLogExporter(endpoint=f"{endpoint}/v1/logs")
    else:
        connection_string = os.getenv("AZURE_MONITOR_CONNECTION_STRING")
        otlp_log_exporter = AzureMonitorLogExporter(connection_string=connection_string)
        
    # Configure logging with OTLP
    logger_provider = LoggerProvider(resource=resource)
    set_logger_provider(logger_provider)
   
    # Create OTLP log exporter
    log_record_processor = BatchLogRecordProcessor(otlp_log_exporter)
    logger_provider.add_log_record_processor(log_record_processor)
    
    # Create and set up the OTLP handler
    otlp_handler = LoggingHandler(level=logging.NOTSET, logger_provider=logger_provider)
    
    # Create a console handler for logging to the console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter("[CONSOLE] %(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    
    # Set up the root logger with both handlers
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)  # Set the desired log level
    root_logger.addHandler(otlp_handler)
    root_logger.addHandler(console_handler)
    
    # Return the configured logger
    return logging.getLogger("example-logger")

def main():
    # Set up logging
    logger = setup_logging(is_local=True)
    
    # Use the logger to log different levels
    logger.info("This is an informational message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    logger.info("Operation completed")

if __name__ == "__main__":
    main()
    # Keep the application running briefly to allow the batch processors to export
    import time
    time.sleep(20)  # Wait for 20 seconds to ensure logs are exported
    print("Script execution completed.")
