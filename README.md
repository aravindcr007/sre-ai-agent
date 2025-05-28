# AIOps SRE AI Agent

This project is an AI-powered agent designed to assist Site Reliability Engineers (SREs) and AIOps teams by providing a conversational interface to query AWS resources, visualize metrics, inspect logs, and receive suggestions for remediations. The application is built using Streamlit and leverages a Gemini-based agent for its core logic.

## Features

- **Conversational Interface:** Ask questions about your AWS resources in natural language.
- **AWS Data Retrieval:**
    - Fetch metrics for various AWS services (e.g., CPUUtilization, MemoryUtilization).
    - Retrieve logs from CloudWatch Logs.
    - Get overviews of your cloud workloads.
    - List running services (EC2, ECS, Lambda, etc.).
    - Check node counts for clusters and Auto Scaling Groups.
- **Data Visualization:**
    - Plot time-series data for metrics.
    - Display log data and other information in tables.
- **Remediation Suggestions:**
    - Receive suggestions for scaling actions based on current metrics (e.g., for EC2 Auto Scaling Groups, ECS Services).
- **Mock Data Mode:** Option to use a mock API endpoint for development and testing without making actual AWS calls.

## Core Technologies

- **Streamlit:** For the web application interface.
- **Langchain with Google Generative AI (Gemini):** Powers the AI agent and tool interactions.
- **AWS SDK (Boto3):** For interacting with AWS services (when not in mock mode).
- **Plotly & Pandas:** For data visualization and manipulation.

## Project Structure

```
.
├── streamlit_app.py            # Main Streamlit application
├── gemini_agent.py             # Core logic for the AI agent, tools, and Langchain integration
├── aws_utils.py                # Utilities for interacting with AWS
├── plotting_utils.py           # Utilities for creating plots and tables
├── config.py                   # Configuration for API keys, mock API endpoint, etc.
├── requirements.txt            # Python dependencies
├── .gitignore                  # Files and directories ignored by Git
├── lambda_function.py          # lambda function to generare logs in AWS cloudwatch
└── README.md                   # This file
```

## Setup and Installation

1.  **Clone the repository:**
    ```bash
    git clone <your-repository-url>
    cd <your-repository-name>
    ```

2.  **Create and activate a virtual environment (recommended):**
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure API Keys and Endpoints:**
    *   You will need a Google API Key for the Gemini model.
    *   If using the mock API, ensure the endpoint is correctly configured.
    *   Update `config.py` with your `GOOGLE_API_KEY`.
    *   If you have a mock API Gateway endpoint, set `MOCK_API_ENDPOINT` in `config.py`. If it's set to `"YOUR_API_GATEWAY_INVOKE_URL_HERE"`, the mock functionality will show a warning.
    *   If you intend to use real AWS calls (by unchecking "Use Mock Data API" in the UI), ensure your environment is configured with AWS credentials (e.g., via AWS CLI, IAM roles).

## How to Run

1.  Ensure your virtual environment is activated and dependencies are installed.
2.  Run the Streamlit application:
    ```bash
    streamlit run streamlit_app.py
    ```
3.  Open your web browser and navigate to the local URL provided by Streamlit (usually `http://localhost:8501`).

## Usage

-   The sidebar allows you to toggle between using the mock data source or attempting real AWS calls.
-   A list of example queries is provided in the sidebar to get you started.
-   Type your questions or requests into the chat input at the bottom of the page.
-   Use the "Clear Chat History & Context" button to reset the conversation.

## Example Queries

-   "Plot CPU utilization for ec2-instance-A."
-   "Show memory usage for ecs-service-X for the last 3 hours as a table."
-   "Get ERROR logs for lambda-function-Y since yesterday."
-   "What is the workload currently running?"
-   "What are the names of the services running currently?"
-   "CPU on high-load-service is at 88% and it's an EC2 AutoScalingGroup, suggest scaling up and tell me the root cause."

## Contributing

(Add guidelines for contributions if this is an open project)

## License

(Specify a license if applicable) 