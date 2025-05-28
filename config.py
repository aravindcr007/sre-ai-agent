# config.py
import os

# IMPORTANT: Set your Google API Key as an environment variable
# or replace os.environ.get("GOOGLE_API_KEY") directly with your key (less secure for sharing).
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

AWS_REGION = "eu-north-1"  # Or your preferred AWS region for real CloudWatch calls
MOCK_API_ENDPOINT = "https://sle6bk9o6e.execute-api.eu-north-1.amazonaws.com" # e.g., "https://abc123xyz.execute-api.eu-north-1.amazonaws.com"

# For demo purposes and mocking
MOCK_SERVICES = {
    "ec2-instance-A": {"type": "EC2", "log_group": "/aws/ec2/ec2-instance-A-applogs"},
    "ecs-service-X": {"type": "ECS", "log_group": "/aws/ecs/ecs-service-X-cluster/ecs-service-X"},
    "lambda-function-Y": {"type": "Lambda", "log_group": "/aws/lambda/lambda-function-Y"},
    "rds-database-Z": {"type": "RDS", "log_group": "/aws/rds/instance/rds-database-Z/error"}, # Example log group
    "high-load-service": {"type": "Generic", "log_group": "/app/high-load-service"},
    "spiky-service": {"type": "Generic", "log_group": "/app/spiky-service"},
    "my-custom-backend-service": {"type": "Generic", "log_group": "my-custom-backend-service"},
    "my-ec2-app-prod-logs": {"type": "EC2", "log_group": "my-ec2-app-prod-logs"},
    "/aws/lambda/lambda-mock-data": {"type": "Lambda", "log_group": "/aws/lambda/lambda-mock-data"},
    "/aws/lambda/lambda-mock-data/appService": {"type": "Lambda", "log_group": "/aws/lambda/lambda-mock-data/appService"},
    "transaction-processor": {"type": "Generic", "log_group": "transaction-processor"},
    "my-generic-app-logs": {"type": "Generic", "log_group": "my-generic-app-logs"}
}

MOCK_METRICS = [
    "CPUUtilization", "MemoryUtilization", "NetworkIn", "NetworkOut",
    "DiskReadOps", "DiskWriteOps", "DatabaseConnections", "Invocations", "Errors"
]

# Helper to get log group for a service if defined, otherwise use a generic pattern
def get_log_group_for_service(service_name_or_log_group):
    if service_name_or_log_group in MOCK_SERVICES:
        return MOCK_SERVICES[service_name_or_log_group]["log_group"]
    # If it looks like a path, use it directly
    if "/" in service_name_or_log_group:
        return service_name_or_log_group
    # Fallback for generic service names not explicitly in MOCK_SERVICES
    return f"/app/logs/{service_name_or_log_group}"