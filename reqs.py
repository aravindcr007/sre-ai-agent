import requests
import config

# For metrics
metrics_params = {
    "service_name": "high-load-service",
    "metric_name": "CPUUtilization",
    "start_time": "2025-05-07T10:00:00Z",
    "end_time": "2025-05-07T11:00:00Z"
}
try:
    response = requests.get(f"{config.MOCK_API_ENDPOINT}/metrics", params=metrics_params, timeout=10)
    response.raise_for_status()
    print("Metrics Response JSON:", response.json())
except requests.RequestException as e:
    print(f"Error fetching mock metrics: {e}")


logs_params = {
    "log_group_name": "/aws/lambda/lambda-function-Y",
    "filter_pattern": "WARN",
    "limit": 5
}
try:
    response = requests.get(f"{config.MOCK_API_ENDPOINT}/logs", params=logs_params, timeout=10)
    response.raise_for_status()
    print("Logs Response JSON:", response.json())
except requests.RequestException as e:
    print(f"Error fetching mock logs: {e}")