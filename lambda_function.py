import json
import random
import datetime
import time
import uuid

def generate_metric_data(service_name, metric_name, start_time_iso, end_time_iso, period_seconds=300):
    timestamps = []
    values = []
    try:
        start_dt = datetime.datetime.fromisoformat(start_time_iso.replace("Z", "+00:00"))
        end_dt = datetime.datetime.fromisoformat(end_time_iso.replace("Z", "+00:00"))
    except ValueError as e:
        raise ValueError(f"Invalid ISO date format for start_time_iso or end_time_iso: {e}. Ensure format like YYYY-MM-DDTHH:MM:SSZ. Got: '{start_time_iso}', '{end_time_iso}'")

    current_dt = start_dt
    period_delta = datetime.timedelta(seconds=int(period_seconds))

    while current_dt <= end_dt:
        timestamps.append(current_dt.isoformat(timespec='seconds'))
        
        val = 0.0
        if "CPU" in metric_name.upper():
            if "high-load-service" in service_name:
                val = round(random.uniform(75.0, 95.0), 2)
            elif "spiky-service" in service_name and random.random() < 0.3:
                 val = round(random.uniform(60.0, 90.0), 2)
            else:
                val = round(random.uniform(10.0, 40.0), 2)
        elif "Memory" in metric_name.upper():
            val = round(random.uniform(40.0, 75.0), 2)
        elif "NetworkIn" in metric_name or "NetworkOut" in metric_name:
            val = round(random.uniform(100000.0, 5000000.0), 0)
        elif "Disk" in metric_name:
            val = round(random.uniform(10.0, 200.0), 0)
        elif "DatabaseConnections" in metric_name:
            val = round(random.uniform(5.0, 50.0), 0)
        elif "Invocations" in metric_name:
            val = round(random.uniform(100.0, 1000.0), 0)
        elif "Errors" in metric_name:
             val = round(random.uniform(0.0, 5.0), 0)
        else:
            val = round(random.uniform(0.0, 100.0), 2)
        values.append(val)
        
        if period_delta.total_seconds() == 0:
            break
        current_dt += period_delta
        if len(timestamps) > 1000:
            break
            
    return {"Timestamps": timestamps, "Values": values, "Label": metric_name, "Service": service_name}

def generate_log_events(log_group_name, start_time_epoch_ms, end_time_epoch_ms, filter_pattern=""):
    events = []
    num_events = random.randint(10, 50)
    log_levels = ["INFO", "WARN", "ERROR", "DEBUG"]
    service_short_name = log_group_name.split('/')[-1] if '/' in log_group_name else log_group_name
    service_short_name = service_short_name.replace("-logs", "").replace("-log", "")

    for _ in range(num_events):
        current_start_ms = int(start_time_epoch_ms)
        current_end_ms = int(end_time_epoch_ms)
        if current_start_ms > current_end_ms:
            ts = current_end_ms 
        else:
            ts = random.randint(current_start_ms, current_end_ms)

        level = random.choice(log_levels)
        transaction_id = str(uuid.uuid4())[:8]
        user_id = random.randint(100, 999)
        
        message = f"Timestamp={ts}, Level={level}, Service={service_short_name}, TransactionID={transaction_id}, UserID={user_id}, "
        if level == "ERROR":
            error_codes = ["DB_CONN_TIMEOUT", "NULL_PTR_EX", "AUTH_FAILURE", "DISK_FULL"]
            message += f"Status=FAILED, ErrorCode={random.choice(error_codes)}, Details: Critical error processing request."
        elif level == "WARN":
            warn_messages = ["HighLatencyDetected", "QueueDepthApproachingLimit", "DeprecatedAPICall"]
            message += f"Status=WARNING, WarningType={random.choice(warn_messages)}, Details: Potential issue identified."
        elif level == "INFO":
            info_actions = ["UserLogin", "DataProcessed", "RequestReceived", "TaskCompleted"]
            message += f"Status=SUCCESS, Action={random.choice(info_actions)}, Details: Operation completed as expected."
        else: # DEBUG
            message += f"Status=DEBUG, Details: Debugging information, variable_value={random.randint(0,1024)}."

        # Apply filter_pattern (case-insensitive)
        should_add = True
        if filter_pattern:
            if filter_pattern.lower() not in message.lower():
                should_add = False
            
        if should_add:
            events.append({
                "timestamp": ts, # Epoch milliseconds
                "message": message,
                "ingestionTime": ts + random.randint(10, 100), # Simulate slight delay
                "logStreamName": f"{service_short_name}-stream-{datetime.datetime.fromtimestamp(ts/1000.0, tz=datetime.timezone.utc).strftime('%Y-%m-%d-%H')}-{random.randint(1,3)}"
            })
    return sorted(events, key=lambda x: x['timestamp'])

def lambda_handler(event, context):
    print(f"Lambda_Query_Param_Handler: Received event: {json.dumps(event)}")

    try:
        request_path = event.get("rawPath") # For HTTP API Payload v2.0
        query_params = event.get("queryStringParameters", {}) if event.get("queryStringParameters") is not None else {}


        print(f"Lambda_Query_Param_Handler: Request Path: {request_path}")
        print(f"Lambda_Query_Param_Handler: Query Parameters: {json.dumps(query_params)}")

        if request_path == "/metrics":
            service_name = query_params.get("service_name")
            metric_name = query_params.get("metric_name")
            
            default_end_time = datetime.datetime.now(datetime.timezone.utc)
            default_start_time = default_end_time - datetime.timedelta(hours=1)
            
            start_time_iso = query_params.get("start_time", default_start_time.isoformat(timespec='seconds').replace("+00:00", "Z"))
            end_time_iso = query_params.get("end_time", default_end_time.isoformat(timespec='seconds').replace("+00:00", "Z"))
            period = query_params.get("period", "300")

            if not service_name or not metric_name:
                return {"statusCode": 400, "body": json.dumps({"error": "Missing required query parameters: 'service_name' and 'metric_name'"})}
            
            metric_data = generate_metric_data(service_name, metric_name, start_time_iso, end_time_iso, int(period))
            return {"statusCode": 200, "body": json.dumps(metric_data)}

        elif request_path == "/logs":
            log_group_name = query_params.get("log_group_name")
            filter_pattern = query_params.get("filter_pattern", "")
            
            default_end_ms = int(time.time() * 1000)
            default_start_ms = int((time.time() - 3600) * 1000) # 1 hour ago

            start_time_ms = query_params.get("start_time", str(default_start_ms))
            end_time_ms = query_params.get("end_time", str(default_end_ms))

            if not log_group_name:
                return {"statusCode": 400, "body": json.dumps({"error": "Missing required query parameter: 'log_group_name'"})}

            log_data = generate_log_events(log_group_name, int(start_time_ms), int(end_time_ms), filter_pattern)
            return {"statusCode": 200, "body": json.dumps({"events": log_data})}
        
        else:
            return {"statusCode": 404, "body": json.dumps({"error": "Not Found: The requested path does not exist or is not configured correctly in API Gateway.", "received_path": request_path})}

    except ValueError as ve:
        print(f"Lambda_Query_Param_Handler: ValueError: {str(ve)}")
        return {"statusCode": 400, "body": json.dumps({"error": "Bad Request", "details": str(ve)})}
    except Exception as e:
        aws_request_id = context.aws_request_id if hasattr(context, 'aws_request_id') else "N/A"
        print(f"Lambda_Query_Param_Handler: Error processing request (ID: {aws_request_id}): {str(e)}")
        import traceback
        print(traceback.format_exc())
        return {"statusCode": 500, "body": json.dumps({"error": "Internal server error", "details": str(e), "requestId": aws_request_id})}