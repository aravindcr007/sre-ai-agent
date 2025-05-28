# plotting_utils.py
import plotly.graph_objects as go
import pandas as pd
import datetime

def create_time_series_plot(metric_data_list):
    fig = go.Figure()
    if not isinstance(metric_data_list, list):
        metric_data_list = [metric_data_list]

    for data in metric_data_list:
        if data and data.get("Timestamps") and data.get("Values") and \
           len(data["Timestamps"]) == len(data["Values"]):
            try:
                timestamps = pd.to_datetime(data["Timestamps"])
                fig.add_trace(go.Scatter(
                    x=timestamps,
                    y=data["Values"],
                    mode='lines+markers',
                    name=data.get("Label", "Metric")
                ))
            except Exception as e:
                print(f"Error processing metric data for plotting: {e}. Data: {data}")
    
    fig.update_layout(
        title="Metrics Over Time",
        xaxis_title="Time (UTC)",
        yaxis_title="Value",
        legend_title="Metrics",
        template="plotly_dark"
    )
    return fig

def create_table_from_logs(log_events_list):
    if not log_events_list:
        return pd.DataFrame(columns=["Timestamp", "Log Stream", "Message"])
        
    processed_events = []
    for event in log_events_list:
        try:
            ts_utc = datetime.datetime.fromtimestamp(event['timestamp'] / 1000.0, tz=datetime.timezone.utc)
            formatted_ts = ts_utc.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3] + " UTC" 
            
            processed_events.append({
                "Timestamp": formatted_ts,
                "Log Stream": event.get('logStreamName', 'N/A'),
                "Message": event.get('message', '')
            })
        except Exception as e:
            print(f"Error processing log event for table: {e}. Event: {event}")
            processed_events.append({
                "Timestamp": "ErrorParsingTimestamp",
                "Log Stream": event.get('logStreamName', 'N/A'),
                "Message": f"Error processing: {event.get('message', '')} ({str(e)})"
            })
            
    return pd.DataFrame(processed_events)

def create_table_from_metrics(metric_data):
    if not metric_data or not metric_data.get("Timestamps") or not metric_data.get("Values") or \
       len(metric_data["Timestamps"]) != len(metric_data["Values"]):
        return pd.DataFrame(columns=["Timestamp", "Value", "Metric"])

    try:
        timestamps_dt = pd.to_datetime(metric_data["Timestamps"])
        formatted_timestamps = [ts.strftime('%Y-%m-%d %H:%M:%S %Z') if pd.notnull(ts) else 'N/A' for ts in timestamps_dt]

        df = pd.DataFrame({
            "Timestamp": formatted_timestamps,
            "Value": metric_data["Values"],
        })
        df["Metric"] = metric_data.get("Label", "Value") 
        return df
    except Exception as e:
        print(f"Error creating table from metrics: {e}. Data: {metric_data}")
        return pd.DataFrame({"Error": [str(e)]})