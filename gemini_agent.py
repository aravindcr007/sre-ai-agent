# gemini_agent.py (System Message Fix & RCA Tool Message Fix)

import sys

import config
import aws_utils 
import requests
import json
import datetime
import time
import random 

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import Tool
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage

_USE_MOCK_DATA_GLOBALLY = True

class GetAWSMetricToolInput(BaseModel):
    service_name: str = Field(description="The name or ID of the AWS service/resource (e.g., 'ec2-instance-A'). REQUIRED.")
    metric_name: str = Field(description="The name of the metric (e.g., 'CPUUtilization', 'MemoryUtilization'). REQUIRED.")
    time_range_str: str = Field(default="last hour", description="Natural language time duration for the metric data (e.g., 'last 3 hours'). Defaults to 'last hour'.")
    statistic: str = Field(default="Average", description="The statistic to retrieve (e.g., 'Average', 'Sum'). Defaults to 'Average'.")
    period_seconds: int = Field(default=0, description="Granularity in seconds (e.g., 60, 300). Defaults to auto-calculated (0 means auto).")

class GetAWSLogsToolInput(BaseModel):
    service_or_log_group_name: str = Field(description="Service name (e.g., 'ecs-service-X') or full CloudWatch Log Group name. REQUIRED.")
    time_range_str: str = Field(default="last hour", description="Natural language time duration for logs. Defaults to 'last hour'.")
    filter_pattern: str = Field(default="", description="CloudWatch Logs filter pattern (e.g., 'ERROR'). Optional.")
    limit: int = Field(default=50, description="Maximum number of log events. Defaults to 50.")

class SuggestScalingActionToolInput(BaseModel):
    service_name: str = Field(description="Name of the AWS service experiencing high load. REQUIRED.")
    service_type: str = Field(description="Type of the AWS service (e.g., 'ECS Service', 'EC2 AutoScalingGroup'). REQUIRED.")
    metric_name: str = Field(description="Name of the metric that is high (e.g., 'CPUUtilization'). REQUIRED.")
    current_metric_value: str = Field(description="Current high metric value (e.g., '90%', '85'). REQUIRED.")

class GetCloudWorkloadOverviewToolInput(BaseModel):
    filter_criteria: str = Field(default="", description="Optional filter criteria like environment (e.g., 'production') or application name if known by user.")

class ListRunningServicesToolInput(BaseModel):
    service_type_filter: str = Field(default="", description="Optional filter for service type (e.g., 'Lambda', 'ECS', 'EC2'). If empty, attempts to list key services or asks for clarification.")
    application_tag_or_prefix: str = Field(default="", description="Optional tag or naming prefix to filter services, especially useful for Lambda apps.")

class GetClusterNodeCountToolInput(BaseModel):
    cluster_or_asg_name: str = Field(description="The name of the ECS cluster, EKS cluster, or EC2 Auto Scaling Group. REQUIRED if user implies a specific cluster.")


def tool_get_aws_metric(service_name: str, metric_name: str, 
                        time_range_str: str = "last hour", 
                        statistic: str = "Average", 
                        period_seconds: int = 0) -> dict:
    global _USE_MOCK_DATA_GLOBALLY
    print(f"TOOL_FUNC: tool_get_aws_metric called with: service_name='{service_name}', metric_name='{metric_name}', "
          f"time_range_str='{time_range_str}', statistic='{statistic}', period_seconds={period_seconds}, "
          f"use_mock_data={_USE_MOCK_DATA_GLOBALLY}")

    start_dt_utc, end_dt_utc = aws_utils.parse_time_range(time_range_str)

    if period_seconds == 0:
        duration_hours = (end_dt_utc - start_dt_utc).total_seconds() / 3600
        if duration_hours <= 1: period_seconds = 60
        elif duration_hours <= 6: period_seconds = 300
        else: period_seconds = 3600
    
    print(f"TOOL_FUNC: Calculated period: {period_seconds}s for time range '{time_range_str}'")

    if _USE_MOCK_DATA_GLOBALLY:
        mock_params = {
            "service_name": service_name, "metric_name": metric_name,
            "start_time": start_dt_utc.isoformat().replace("+00:00", "Z"),
            "end_time": end_dt_utc.isoformat().replace("+00:00", "Z"),
            "period": period_seconds
        }
        try:
            response = requests.get(f"{config.MOCK_API_ENDPOINT}/metrics", params=mock_params, timeout=15)
            response.raise_for_status()
            return response.json() 
        except requests.RequestException as e:
            return {"error": f"Mock API call failed for metrics: {str(e)}"}
    else: 
        cw_params = aws_utils.get_cw_params_for_service(service_name, metric_name)
        if not cw_params or "namespace" not in cw_params or "dimensions" not in cw_params:
             return {"error": f"Could not determine CloudWatch parameters for service '{service_name}'."}
        return aws_utils.get_metric_data_from_cw(
            namespace=cw_params["namespace"], metric_name=metric_name, dimensions=cw_params["dimensions"],
            start_time=start_dt_utc, end_time=end_dt_utc, period=period_seconds, statistic=statistic
        )

def tool_get_aws_logs(service_or_log_group_name: str, 
                      time_range_str: str = "last hour", 
                      filter_pattern: str = "", 
                      limit: int = 50) -> dict:
    global _USE_MOCK_DATA_GLOBALLY
    print(f"TOOL_FUNC: tool_get_aws_logs called with: name='{service_or_log_group_name}', "
          f"time_range_str='{time_range_str}', filter='{filter_pattern}', limit={limit}, "
          f"use_mock_data={_USE_MOCK_DATA_GLOBALLY}")
    
    start_dt_utc, end_dt_utc = aws_utils.parse_time_range(time_range_str)
    start_time_ms = int(start_dt_utc.timestamp() * 1000)
    end_time_ms = int(end_dt_utc.timestamp() * 1000)
    actual_log_group_name = config.get_log_group_for_service(service_or_log_group_name)

    if _USE_MOCK_DATA_GLOBALLY:
        mock_params = {
            "log_group_name": actual_log_group_name, "start_time": start_time_ms, "end_time": end_time_ms,
            "filter_pattern": filter_pattern, "limit": limit
        }
        try:
            response = requests.get(f"{config.MOCK_API_ENDPOINT}/logs", params=mock_params, timeout=15)
            response.raise_for_status()
            return response.json() 
        except requests.RequestException as e:
            return {"error": f"Mock API call failed for logs: {str(e)}"}
    else: 
        return aws_utils.get_logs_from_cw(
            log_group_name=actual_log_group_name, start_time_epoch_ms=start_time_ms,
            end_time_epoch_ms=end_time_ms, filter_pattern=filter_pattern, limit=limit
        )

def tool_suggest_scaling_action(service_name: str, service_type: str, 
                                metric_name: str, current_metric_value: str) -> dict:
    print(f"TOOL_FUNC: tool_suggest_scaling_action called with: service_name='{service_name}', "
          f"service_type='{service_type}', metric_name='{metric_name}', value='{current_metric_value}'")
    
    script = f"# Suggested action for scaling {service_type} '{service_name}' due to high {metric_name} ({current_metric_value}):\n"
    if "EC2 AutoScalingGroup" in service_type or "ASG" in service_type.upper():
        script += (f"aws autoscaling set-desired-capacity --auto-scaling-group-name \"{service_name}\" --desired-capacity NEW_DESIRED_VALUE\n"
                   f"# Replace NEW_DESIRED_VALUE. Check current: aws autoscaling describe-auto-scaling-groups --auto-scaling-group-names \"{service_name}\" --query \"AutoScalingGroups[0].DesiredCapacity\"")
    elif "ECS Service" in service_type:
        cluster_name_placeholder = "your-ecs-cluster" 
        actual_service_name = service_name
        if "/" in service_name: 
            parts = service_name.split('/')
            if len(parts) == 2:
                cluster_name_placeholder = parts[0]
                actual_service_name = parts[1]
        script += (f"aws ecs update-service --cluster \"{cluster_name_placeholder}\" --service \"{actual_service_name}\" --desired-count NEW_DESIRED_COUNT\n"
                   f"# Replace NEW_DESIRED_COUNT. Check current: aws ecs describe-services --cluster \"{cluster_name_placeholder}\" --services \"{actual_service_name}\" --query \"services[0].desiredCount\"")
    else:
        script += f"# Specific CLI/Boto3 script for scaling '{service_name}' (type: {service_type}) needs to be developed."

    return { 
        "suggestion_text": f"High {metric_name} ({current_metric_value}) on {service_name} ({service_type}). Consider scaling up.", 
        "script_suggestion": script
    }

def tool_get_cloud_workload_overview(filter_criteria: str = "") -> dict:
    print(f"TOOL_FUNC: tool_get_cloud_workload_overview called with filter: '{filter_criteria}'")
    mock_workload = {
        "key_applications": [
            {"name": "OrderProcessingSystem", "type": "ECS", "status": "Healthy", "primary_components": ["ecs-service-X", "rds-database-Z"]},
            {"name": "UserAuthentication", "type": "Lambda", "status": "Healthy", "primary_components": ["lambda-function-Y"]},
            {"name": "DataAnalyticsPlatform", "type": "EC2", "status": "Warning (High CPU on ec2-instance-A)", "primary_components": ["ec2-instance-A", "spiky-service"]}
        ],
        "summary_text": "Currently, our key workloads include Order Processing, User Authentication, and Data Analytics. Most systems are healthy, but the Data Analytics platform shows high CPU on one of its EC2 instances."
    }
    if filter_criteria:
        return {"overview_text": f"For criteria '{filter_criteria}', I'd normally show specific details. For now, here's a general overview: {mock_workload['summary_text']} (This is mock data)."}
    return {"overview_text": mock_workload["summary_text"] + " (This is mock data). You can ask for details on specific applications mentioned."}

def tool_list_running_services(service_type_filter: str = "", application_tag_or_prefix: str = "") -> dict:
    print(f"TOOL_FUNC: tool_list_running_services called with type_filter: '{service_type_filter}', app_filter: '{application_tag_or_prefix}'")
    services = [
        {"name": "ec2-instance-A", "type": "EC2", "app_group": "Analytics"},
        {"name": "ecs-service-X", "type": "ECS", "app_group": "OrderProcessing"},
        {"name": "lambda-function-Y", "type": "Lambda", "app_group": "UserAuth"},
        {"name": "billing-lambda-processor", "type": "Lambda", "app_group": "Billing"},
        {"name": "rds-database-Z", "type": "RDS", "app_group": "OrderProcessing"},
        {"name": "high-load-service-asg", "type": "EC2 AutoScalingGroup", "app_group": "Generic"},
    ]
    filtered_services = services
    if service_type_filter:
        filtered_services = [s for s in filtered_services if service_type_filter.lower() in s["type"].lower()]
    if application_tag_or_prefix:
        filtered_services = [s for s in filtered_services if application_tag_or_prefix.lower() in s["name"].lower() or application_tag_or_prefix.lower() in s["app_group"].lower()]

    if not filtered_services:
        return {"services_text": "No specific services found matching your criteria with mock data. Key services include ec2-instance-A (EC2), ecs-service-X (ECS), and lambda-function-Y (Lambda)."}
    
    service_list_str = ", ".join([f"{s['name']} ({s['type']})" for s in filtered_services])
    return {"services_list": filtered_services, "services_text": f"Currently running services (mock data) matching your query: {service_list_str}."}

def tool_get_cluster_node_count(cluster_or_asg_name: str = "") -> dict:
    print(f"TOOL_FUNC: tool_get_cluster_node_count called for: '{cluster_or_asg_name}'")
    if not cluster_or_asg_name:
        return {"node_count_text": "Please specify the name of the cluster or Auto Scaling Group for which you want the node count."}
    return {"node_count_text": f"Mock: The cluster/ASG '{cluster_or_asg_name}' currently has {random.randint(2, 8)} running nodes/instances. (This is mock data)."}


_llm_with_tools = None
_tools_map = {
    "GetAWSMetric": tool_get_aws_metric,
    "GetAWSLogs": tool_get_aws_logs,
    "SuggestScalingAction": tool_suggest_scaling_action,
    "GetCloudWorkloadOverview": tool_get_cloud_workload_overview,
    "ListRunningServices": tool_list_running_services,
    "GetClusterNodeCount": tool_get_cluster_node_count,
}

SYSTEM_INSTRUCTION_EXPANDED = (
    "You are an expert AIOps assistant. Your primary purpose is to help users query AWS service metrics and logs, "
    "understand the state of their services, and get suggestions for remediation. You have tools to fetch data and provide information."
    "\n\nGeneral Query Handling:"
    "\n- If a user's query is too broad (e.g., 'What's the CPU utilization?', 'How many nodes are running?', 'What is the workload Currently running?', 'What is the name of the services which are running currently?'), "
    "  you MUST first try to use an appropriate overview or listing tool (like 'GetCloudWorkloadOverview' or 'ListRunningServices'). If the tool itself indicates it needs more specifics, or if no such broad tool is suitable, "
    "  then you MUST ask clarifying questions to narrow down the scope. For example, ask for specific service names, cluster names, application identifiers, or time ranges."
    "\n- For 'How many nodes are running?', if no cluster/ASG is specified, use 'GetClusterNodeCount' but expect it to ask for the name. Your response should then ask the user for the name."
    "\n- For 'What is the name of the services which are running currently?', use the 'ListRunningServices' tool. You can pass an empty filter if none is implied by the user."
    "\n- For 'What is the name of the App which is hosted on Lambda?', use the 'ListRunningServices' tool with 'service_type_filter' as 'Lambda'."
    "\n\nWhen a user asks for a graph, plot, chart, or to visualize metrics:"
    "\n1. Use your 'GetAWSMetric' tool to retrieve the requested metric data."
    "\n2. Once the tool successfully returns the data, your textual response should confirm data retrieval and mention that the application will display the graph. "
    "   Example: 'Okay, I've retrieved the CPUUtilization data for ec2-instance-A. The application will now show the graph.'"
    "\n3. Do NOT state that you 'cannot display a graph'. The application handles rendering."
    "\n\nRoot Cause Suggestion (Rudimentary) for High CPU/Memory:"
    "\n- If the 'GetAWSMetric' tool is used and indicates a significantly high critical metric (e.g., CPUUtilization > 80%, MemoryUtilization > 85%) for a specific service, "
    "  the system will automatically attempt to fetch relevant ERROR logs for that same service and time period. "
    "  When you summarize, if both high metrics and error logs were found (or if no errors were found despite high metrics), synthesize this information. "
    "  Example: 'CPU for service X is high (90%). I also found several 'OutOfMemory' errors around the same time. This could be a contributing factor.' "
    "  Or: 'Memory for service Y is high (92%), but no specific error logs were found in that period. You might want to check application-specific dashboards or recent deployments.'"
    "\n\nRemediation Actions / Scaling Suggestions:"
    "\n- If a user asks for a 'remediation action' or how to fix high utilization, and they provide necessary details (service name, type, metric, value), use the 'SuggestScalingAction' tool."
    "\n\nReporting:"
    "\n- If a user asks for a 'report' (e.g., 'CPU utilization report'), ask for specifics: 'For which service and time period? Would you like a table or a graphical summary?' Then use the GetAWSMetric tool accordingly."
    "\n\nTool Usage:"
    "\n- Always use the Pydantic schema provided for each tool to structure your arguments correctly."
    "\n- If a tool call is successful, briefly summarize what data you've obtained or what action was prepared."
    "\n- If a tool call results in an error, clearly inform the user about the error and, if appropriate, ask for corrected information."
    "\n\nDefault Behaviors:"
    "\n- Time range for metrics/logs: 'last hour' if not specified."
    "\n- Metric statistic: 'Average' if not specified."
    "\n- Metric period: Auto-calculated based on time range if not specified."
    "\n\nBe helpful, concise, and focus on fulfilling the user's AIOps requests by effectively using your tools or asking for clarification."
)


def get_llm_with_tools():
    global _llm_with_tools
    if _llm_with_tools is None:
        if not config.GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY is not configured.")
        
        print("LANGCHAIN_DIRECT: Initializing LLM with tools (Expanded)...")
        llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro-latest",
                                     google_api_key=config.GOOGLE_API_KEY,
                                     temperature=0.1, 
                                     )
        
        langchain_tools = [
            Tool(name="GetAWSMetric", func=tool_get_aws_metric, description="Fetches time-series metrics for an AWS service. Use for queries about CPU, memory, network, disk, invocations, etc., or when asked to plot/graph/chart metrics.", args_schema=GetAWSMetricToolInput),
            Tool(name="GetAWSLogs", func=tool_get_aws_logs, description="Fetches logs for an AWS service or log group. Use for queries about errors, warnings, or specific log messages.", args_schema=GetAWSLogsToolInput),
            Tool(name="SuggestScalingAction", func=tool_suggest_scaling_action, description="Suggests scaling actions (CLI commands) for AWS services under high load. Use when user mentions high resource usage and asks for remediation or scaling help.", args_schema=SuggestScalingActionToolInput),
            Tool(name="GetCloudWorkloadOverview", func=tool_get_cloud_workload_overview, description="Provides a high-level summary of active key services or workloads. Use if the user asks a very broad question like 'What is the workload currently running on cloud?'. This tool will likely ask for more specific filters if its initial response is too generic.", args_schema=GetCloudWorkloadOverviewToolInput),
            Tool(name="ListRunningServices", func=tool_list_running_services, description="Lists running services, potentially filtered by type (e.g., Lambda, ECS) or application tags/prefixes. Use if the user asks 'What is the name of the services which are running currently?' or 'What apps are hosted on Lambda?'. For the Lambda app query, set service_type_filter to 'Lambda'.", args_schema=ListRunningServicesToolInput),
            Tool(name="GetClusterNodeCount", func=tool_get_cluster_node_count, description="Gets the number of running nodes/instances for a specified cluster or Auto Scaling Group. Use if the user asks 'How many nodes are running?'. If no cluster/ASG name is given by the user, this tool will ask for it.", args_schema=GetClusterNodeCountToolInput),
        ]
        _llm_with_tools = llm.bind_tools(langchain_tools)
        print("LANGCHAIN_DIRECT: LLM with tools initialized (system instruction will be prepended to invoke).")
    return _llm_with_tools

_conversation_history = [] 

def get_langchain_direct_tool_call_response(user_query: str, use_mock_data: bool) -> dict:
    global _USE_MOCK_DATA_GLOBALLY, _conversation_history
    _USE_MOCK_DATA_GLOBALLY = use_mock_data 

    if not config.GOOGLE_API_KEY:
         return {"text_summary": "Error: Gemini API Key is not configured.", "data_for_display": None, "tool_used": None, "script_suggestion": None}

    llm_with_tools = get_llm_with_tools()
    
    current_turn_messages_for_llm_decision = [
        SystemMessage(content=SYSTEM_INSTRUCTION_EXPANDED) 
    ] + _conversation_history + [
        HumanMessage(content=user_query)
    ]

    try:
        print(f"LANGCHAIN_DIRECT: Invoking LLM for tool decision with query: '{user_query}'.")
        ai_msg_with_potential_tool_call = llm_with_tools.invoke(current_turn_messages_for_llm_decision)
                
        print(f"LANGCHAIN_DIRECT: LLM AIMessage received. Tool calls: {ai_msg_with_potential_tool_call.tool_calls if hasattr(ai_msg_with_potential_tool_call, 'tool_calls') and ai_msg_with_potential_tool_call.tool_calls else 'None'}")

        messages_for_final_summary = list(current_turn_messages_for_llm_decision)
        messages_for_final_summary.append(ai_msg_with_potential_tool_call)

        if hasattr(ai_msg_with_potential_tool_call, 'tool_calls') and ai_msg_with_potential_tool_call.tool_calls:
            tool_call_request = ai_msg_with_potential_tool_call.tool_calls[0]
            tool_name = tool_call_request['name']
            tool_args = tool_call_request['args']

            print(f"LANGCHAIN_DIRECT: LLM decided to use tool: {tool_name} with args: {tool_args}")

            if tool_name in _tools_map:
                tool_function = _tools_map[tool_name]
                # 2. Execute the primary tool requested by the LLM
                primary_tool_result_data = tool_function(**tool_args)
                
                
                tool_response_content_dict = {"primary_tool_output": primary_tool_result_data}

                # 3. Rudimentary RCA: If high CPU/Memory metric, also fetch error logs
                is_critical_metric_tool = tool_name == "GetAWSMetric"
                metric_name_from_args = tool_args.get("metric_name","").upper() if is_critical_metric_tool else ""
                is_critical_metric_type = "CPU" in metric_name_from_args or "MEMORY" in metric_name_from_args
                
                metric_is_high = False
                if is_critical_metric_tool and is_critical_metric_type and \
                   isinstance(primary_tool_result_data, dict) and "Values" in primary_tool_result_data and primary_tool_result_data["Values"]:
                    numeric_values = [v for v in primary_tool_result_data["Values"] if isinstance(v, (int, float))]
                    if numeric_values:
                        avg_value = sum(numeric_values) / len(numeric_values)
                        if ("CPU" in metric_name_from_args and avg_value > 80) or \
                           ("MEMORY" in metric_name_from_args and avg_value > 85):
                            metric_is_high = True
                
                if metric_is_high:
                    print(f"LANGCHAIN_DIRECT: High critical metric for {tool_args.get('service_name')}. Fetching error logs for RCA.")
                    try:
                        error_log_args = {
                            "service_or_log_group_name": tool_args.get("service_name"),
                            "time_range_str": tool_args.get("time_range_str", "last hour"),
                            "filter_pattern": "ERROR OR Exception OR Timeout OR OOM OR Fail",
                            "limit": 10 
                        }
                        rca_error_logs_data = tool_get_aws_logs(**error_log_args)
                        # Add RCA data to the *content* of the single ToolMessage
                        tool_response_content_dict["rca_error_logs_output"] = rca_error_logs_data
                    except Exception as rca_e:
                        print(f"LANGCHAIN_DIRECT: Error during implicit RCA log fetch: {rca_e}")
                        tool_response_content_dict["rca_error_logs_output"] = {"error": f"Failed to fetch RCA logs: {str(rca_e)}"}
                
                # 4. Create the single ToolMessage responding to the LLM's tool_call_request
                tool_response_message = ToolMessage(
                    content=json.dumps(tool_response_content_dict), 
                    tool_call_id=tool_call_request['id']
                )
                
                messages_for_final_summary.append(tool_response_message)

                # 5. Get final summarization from LLM
                print("LANGCHAIN_DIRECT: Sending combined tool result(s) back to LLM for final summarization.")
                final_ai_msg_summary = llm_with_tools.invoke(messages_for_final_summary) 
                
                # Update persistent history
                _conversation_history.append(HumanMessage(content=user_query))
                _conversation_history.append(ai_msg_with_potential_tool_call)
                _conversation_history.append(tool_response_message)
                _conversation_history.append(final_ai_msg_summary)

                text_summary = final_ai_msg_summary.content if isinstance(final_ai_msg_summary.content, str) else json.dumps(final_ai_msg_summary.content)
                
                script_suggestion = None
                if tool_name == "SuggestScalingAction" and isinstance(primary_tool_result_data, dict) and "script_suggestion" in primary_tool_result_data:
                    script_suggestion = primary_tool_result_data["script_suggestion"]

                return {
                    "text_summary": text_summary,
                    "data_for_display": primary_tool_result_data,
                    "tool_used": tool_name,
                    "script_suggestion": script_suggestion
                }
            else: 
                error_text = f"LLM suggested an unknown tool: {tool_name}"
                _conversation_history.append(HumanMessage(content=user_query))
                _conversation_history.append(ai_msg_with_potential_tool_call)
                _conversation_history.append(AIMessage(content=error_text))
                return {"text_summary": error_text, "data_for_display": None, "tool_used": tool_name, "script_suggestion": None}
        
        else: # No tool call, LLM responded directly
            text_summary = ai_msg_with_potential_tool_call.content if isinstance(ai_msg_with_potential_tool_call.content, str) else json.dumps(ai_msg_with_potential_tool_call.content)
            _conversation_history.append(HumanMessage(content=user_query))
            _conversation_history.append(ai_msg_with_potential_tool_call) 
            return {"text_summary": text_summary, "data_for_display": None, "tool_used": None, "script_suggestion": None}

    except Exception as e:
        print(f"LANGCHAIN_DIRECT: Error during LLM invocation or tool execution: {str(e)}")
        import traceback
        print(traceback.format_exc())
        _conversation_history.append(HumanMessage(content=user_query))
        _conversation_history.append(AIMessage(content=f"An internal error occurred: {str(e)}"))
        return {"text_summary": f"Sorry, an error occurred: {str(e)}", "data_for_display": None, "tool_used": None, "script_suggestion": None}

def clear_conversation_history():
    global _conversation_history
    _conversation_history = []
    print("LANGCHAIN_DIRECT: Conversation history cleared.")

