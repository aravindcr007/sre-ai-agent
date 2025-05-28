# streamlit_app.py
import streamlit as st
import gemini_agent
import plotting_utils 
import pandas as pd
import config 
import json

st.set_page_config(layout="wide", page_title="AIOps SRE AI Agent")

st.title("💬 AIOps SRE AI Agent")
st.caption(f"Ask about AWS metrics, logs, workloads, or request remediations. Mock API")
st.markdown("---")

if "messages" not in st.session_state:
    gemini_agent.clear_conversation_history() 
    st.session_state.messages = [{"role": "assistant", "content": "Hi! How can I help you with your AWS resources today?"}]
if "processing_query" not in st.session_state:
    st.session_state.processing_query = False
if "user_prompt_for_processing" not in st.session_state:
    st.session_state.user_prompt_for_processing = None

with st.sidebar:
    st.header("⚙️ Configuration")
    use_mock_data_source = st.checkbox("Use Mock Data API", value=True,
                                 help="If checked, uses the mock API endpoint. If unchecked, attempts real AWS calls.")

    if use_mock_data_source and config.MOCK_API_ENDPOINT == "YOUR_API_GATEWAY_INVOKE_URL_HERE":
        st.warning("Mock API Endpoint is not configured in `config.py`.")
    
    st.markdown("---")
    st.subheader("Example Queries:")
    examples = [
        "Plot CPU utilization for ec2-instance-A.",
        "Show memory usage for ecs-service-X for the last 3 hours as a table.",
        "Get ERROR logs for lambda-function-Y since yesterday.",
        "What is the workload currently running?", 
        "What are the names of the services running currently?", 
        "How many nodes are running in the 'prod-cluster-asg'?", 
        "What apps are hosted on Lambda with prefix 'billing'?", 
        "CPU on high-load-service is at 88% and it's an EC2 AutoScalingGroup, suggest scaling up and tell me the root cause.",
        "Share the CPU utilization report for rds-database-Z for today."
    ]
    for ex in examples:
        st.markdown(f"- `{ex}`")
    st.markdown("---")
    if st.button("Clear Chat History & Context"):
        gemini_agent.clear_conversation_history() 
        st.session_state.messages = [{"role": "assistant", "content": "Hi! How can I help you with your AWS resources today? (History Cleared)"}]
        st.session_state.processing_query = False
        st.session_state.user_prompt_for_processing = None
        st.rerun()

for message_idx, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        st.markdown(message["content"]) 
        if message["role"] == "assistant":
            if message.get("plot_data"):
                try:
                    fig = plotting_utils.create_time_series_plot(message["plot_data"])
                    st.plotly_chart(fig, use_container_width=True, key=f"plot_{message_idx}")
                except Exception as e_plot:
                    st.error(f"Streamlit: Error trying to plot data: {e_plot}")
            
            if message.get("table_data"):
                try:
                    df_display = None
                    if isinstance(message["table_data"], dict) and "events" in message["table_data"]:
                         df_display = plotting_utils.create_table_from_logs(message["table_data"]["events"])
                    elif isinstance(message["table_data"], dict) and "Timestamps" in message["table_data"]:
                         df_display = plotting_utils.create_table_from_metrics(message["table_data"])
                    elif isinstance(message["table_data"], dict) and "services_list" in message["table_data"]:
                        df_display = pd.DataFrame(message["table_data"]["services_list"])
                    
                    if df_display is not None and not df_display.empty:
                        st.dataframe(df_display, use_container_width=True, key=f"table_{message_idx}")
                    elif df_display is not None: 
                         pass 
                except Exception as e_table:
                    st.error(f"Streamlit: Error trying to display table: {e_table}")

            if message.get("script_suggestion"):
                st.code(message["script_suggestion"], language="bash")
            
            # Display simple text data from new tools if not handled by table/plot
            if message.get("text_data_from_tool"):
                st.markdown(f"**Tool Output:**\n```\n{message['text_data_from_tool']}\n```", unsafe_allow_html=True)


            if message.get("raw_data_debug"): # Keep for debugging if needed
                 with st.expander("View Tool's Raw Data (Debug)"):
                    st.json(message["raw_data_debug"])

if st.session_state.processing_query and st.session_state.user_prompt_for_processing:
    prompt_to_process = st.session_state.user_prompt_for_processing
    
    with st.chat_message("assistant"):
        st.markdown("Thinking... 🧠")
        
    try:
        response_package = gemini_agent.get_langchain_direct_tool_call_response(
            prompt_to_process, 
            use_mock_data=use_mock_data_source
        )
        
        assistant_response_text = response_package.get("text_summary", "Sorry, I didn't get a response.")
        data_for_display = response_package.get("data_for_display")
        tool_used = response_package.get("tool_used")
        script_suggestion = response_package.get("script_suggestion")

        assistant_message_payload = {"role": "assistant", "content": assistant_response_text}

        if data_for_display:
            assistant_message_payload["raw_data_debug"] = data_for_display 
            if isinstance(data_for_display, dict) and "error" in data_for_display:
                print(f"Error from data source tool: {data_for_display['error']}")
            elif tool_used == "GetAWSMetric":
                user_wants_plot = any(kw in prompt_to_process.lower() for kw in ["plot", "graph", "chart", "visualize", "trend", "report"]) # Treat report as plot for now
                user_wants_table = "table" in prompt_to_process.lower()
                if user_wants_table and not user_wants_plot:
                    assistant_message_payload["table_data"] = data_for_display
                else: 
                    assistant_message_payload["plot_data"] = data_for_display
            elif tool_used == "GetAWSLogs":
                assistant_message_payload["table_data"] = data_for_display
            elif tool_used == "ListRunningServices" and "services_list" in data_for_display:
                assistant_message_payload["table_data"] = data_for_display # Will be handled by table logic
            elif tool_used in ["GetCloudWorkloadOverview", "GetClusterNodeCount"] and isinstance(data_for_display, dict):
                if data_for_display.get("overview_text"):
                    assistant_message_payload["text_data_from_tool"] = data_for_display.get("overview_text")
                elif data_for_display.get("services_text"):
                     assistant_message_payload["text_data_from_tool"] = data_for_display.get("services_text")
                elif data_for_display.get("node_count_text"):
                    assistant_message_payload["text_data_from_tool"] = data_for_display.get("node_count_text")
        
        if script_suggestion:
            assistant_message_payload["script_suggestion"] = script_suggestion
        
        st.session_state.messages.append(assistant_message_payload)

    except Exception as e:
        print(f"STREAMLIT_APP: Error processing user prompt: {e}")
        import traceback
        traceback.print_exc()
        error_text = f"An application error occurred: {str(e)}"
        st.session_state.messages.append({"role": "assistant", "content": error_text})
    finally:
        st.session_state.processing_query = False
        st.session_state.user_prompt_for_processing = None
        st.rerun() 


user_prompt_input = st.chat_input("Ask your AIOps question...")
if user_prompt_input and not st.session_state.processing_query:
    st.session_state.messages.append({"role": "user", "content": user_prompt_input})
    st.session_state.user_prompt_for_processing = user_prompt_input
    st.session_state.processing_query = True
    st.rerun() 
