# aws_utils.py
import boto3
import datetime
import time
from botocore.exceptions import ClientError
import config 

_cloudwatch_client = None
_logs_client = None

def get_cloudwatch_client():
    global _cloudwatch_client
    if _cloudwatch_client is None:
        _cloudwatch_client = boto3.client('cloudwatch', region_name=config.AWS_REGION)
    return _cloudwatch_client

def get_logs_client():
    global _logs_client
    if _logs_client is None:
        _logs_client = boto3.client('logs', region_name=config.AWS_REGION)
    return _logs_client

def get_metric_data_from_cw(namespace, metric_name, dimensions, start_time, end_time, period, statistic):
    """
    Fetches metric data from AWS CloudWatch.
    Dimensions example: [{'Name': 'InstanceId', 'Value': 'i-12345'}]
    """
    client = get_cloudwatch_client()
    try:
        response = client.get_metric_data(
            MetricDataQueries=[
                {
                    'Id': 'm1',
                    'MetricStat': {
                        'Metric': {
                            'Namespace': namespace,
                            'MetricName': metric_name,
                            'Dimensions': dimensions
                        },
                        'Period': period,
                        'Stat': statistic,
                    },
                    'ReturnData': True,
                },
            ],
            StartTime=start_time, 
            EndTime=end_time,
            ScanBy='TimestampAscending'
        )
        if response['MetricDataResults'] and response['MetricDataResults'][0]['Timestamps']:
            timestamps_iso = [ts.isoformat() for ts in response['MetricDataResults'][0]['Timestamps']]
            return {
                "Timestamps": timestamps_iso,
                "Values": response['MetricDataResults'][0]['Values'],
                "Label": f"{metric_name} ({statistic})"
            }
        return {"Timestamps": [], "Values": [], "Label": f"{metric_name} ({statistic}) - No data"}
    except ClientError as e:
        print(f"Error fetching metric data from CloudWatch for {metric_name}: {e}")
        return {"error": str(e), "metric_name": metric_name}

def get_logs_from_cw(log_group_name, start_time_epoch_ms, end_time_epoch_ms, filter_pattern="", limit=50):
    client = get_logs_client()
    try:
        params = {
            'logGroupName': log_group_name,
            'startTime': start_time_epoch_ms,
            'endTime': end_time_epoch_ms,
            'limit': limit,
            'interleaved': True
        }
        if filter_pattern:
            params['filterPattern'] = filter_pattern
        
        response = client.filter_log_events(**params)
        return {"events": response.get('events', [])}
    except ClientError as e:
        print(f"Error fetching logs from CloudWatch for {log_group_name}: {e}")
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
             return {"error": f"Log group '{log_group_name}' not found."}
        return {"error": str(e), "log_group_name": log_group_name}

def get_cw_params_for_service(service_name_from_user, metric_name_or_log_type):
    """
    Maps a user-provided service name to CloudWatch parameters (namespace, dimensions, log_group_name).
    This is a simplified example and needs to be adapted to your specific AWS resource naming and tagging.
    """
    if "/" in service_name_from_user and (metric_name_or_log_type == "log" or service_name_from_user.startswith("/aws/")):
        return {"log_group_name": service_name_from_user}

    if service_name_from_user in config.MOCK_SERVICES:
        service_info = config.MOCK_SERVICES[service_name_from_user]
        service_type = service_info.get("type", "Unknown")
        log_group = service_info.get("log_group", config.get_log_group_for_service(service_name_from_user)) # Use helper

        if service_type == "EC2":
            return {
                "namespace": "AWS/EC2",
                "dimensions": [{'Name': 'InstanceId', 'Value': service_name_from_user}], # Assuming name is ID
                "log_group_name": log_group
            }
        elif service_type == "ECS":
            # ECS requires ClusterName and ServiceName. This is a simplification.
            # You might need to pass "ClusterName/ServiceName" as service_name_from_user
            # or have a more sophisticated lookup.
            cluster_name = "default-cluster" # Placeholder
            ecs_service_name = service_name_from_user
            if "/" in service_name_from_user: # Assume ClusterName/ServiceName format
                cluster_name, ecs_service_name = service_name_from_user.split('/', 1)
            return {
                "namespace": "AWS/ECS",
                "dimensions": [
                    {'Name': 'ClusterName', 'Value': cluster_name},
                    {'Name': 'ServiceName', 'Value': ecs_service_name}
                ],
                "log_group_name": log_group
            }
        elif service_type == "Lambda":
            return {
                "namespace": "AWS/Lambda",
                "dimensions": [{'Name': 'FunctionName', 'Value': service_name_from_user}],
                "log_group_name": log_group
            }
        elif service_type == "RDS":
            return {
                "namespace": "AWS/RDS",
                "dimensions": [{'Name': 'DBInstanceIdentifier', 'Value': service_name_from_user}],
                "log_group_name": log_group
            }
        else: # Generic or types from MOCK_SERVICES not explicitly handled for metrics
             return {
                "namespace": "Custom/Namespace", # Placeholder
                "dimensions": [{'Name': 'ServiceName', 'Value': service_name_from_user}],
                "log_group_name": log_group
            }
    else: # Fallback if not in MOCK_SERVICES
        print(f"Service '{service_name_from_user}' not found in MOCK_SERVICES config for detailed CW params. Using generic fallback.")
        return {
            "namespace": "Custom/Namespace", # Placeholder - user might need to be more specific
            "dimensions": [{'Name': 'ServiceName', 'Value': service_name_from_user}],
            "log_group_name": config.get_log_group_for_service(service_name_from_user)
        }


def parse_time_range(time_range_str: str, current_time_utc=None):
    """
    Parses simple natural language time ranges to start_time, end_time (UTC datetime objects).
    Returns (start_time_utc, end_time_utc).
    """
    if current_time_utc is None:
        current_time_utc = datetime.datetime.now(datetime.timezone.utc)
    
    end_time = current_time_utc
    time_range_str_lower = time_range_str.lower()

    if "last hour" in time_range_str_lower or "past hour" in time_range_str_lower:
        start_time = end_time - datetime.timedelta(hours=1)
    elif "last 30 minutes" in time_range_str_lower:
        start_time = end_time - datetime.timedelta(minutes=30)
    elif "last 15 minutes" in time_range_str_lower:
        start_time = end_time - datetime.timedelta(minutes=15)
    elif "last 3 hours" in time_range_str_lower:
        start_time = end_time - datetime.timedelta(hours=3)
    elif "last 6 hours" in time_range_str_lower:
        start_time = end_time - datetime.timedelta(hours=6)
    elif "last 12 hours" in time_range_str_lower:
        start_time = end_time - datetime.timedelta(hours=12)
    elif "last 24 hours" in time_range_str_lower or "past day" in time_range_str_lower:
        start_time = end_time - datetime.timedelta(days=1)
    elif "today" in time_range_str_lower: # Assumes "today" means since midnight UTC of the current_time_utc
        start_time = current_time_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    elif "yesterday" in time_range_str_lower:
        end_time = current_time_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        start_time = end_time - datetime.timedelta(days=1)
    # Add more complex parsing here if needed (e.g., "from 9 AM to 5 PM UTC yesterday")
    else: # Default to last 1 hour if not parseable by simple rules
        print(f"Warning: Could not parse time_range_str '{time_range_str}'. Defaulting to last 1 hour.")
        start_time = end_time - datetime.timedelta(hours=1)
        
    return start_time, end_time