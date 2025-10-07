from langchain_litellm import ChatLiteLLM
from langchain.tools import tool
from langchain_core.messages import HumanMessage
import pandas as pd
import streamlit as st
import json
import random
from sqlalchemy import create_engine, text
import csv
import os



# Need to run:
# socat TCP-LISTEN:8000,fork,reuseaddr OPENSSL:aigateway.inteliquent.com:443,verify=0
# In order to get this working

DB_CONFIG = {
    "host": "ssotest.oraclerac.inteliquent.com",
    "port": 1521,  # or 5432 for PostgreSQL
    "sid": "SSOTEST",
    "user": "EMULHERN",
    "password": "emulhern"
}


WORKFLOW_QUERY = ("select ORDER_ID,STEP_INSTANCE_ID,(((UPDATE_DT - INSERT_DT) * 24) * 60) as ELAPSED,"
                  "INSERT_DT,UPDATE_DT,NAME,IS_AUTOMATED_STEP,TYPE_WORKFLOW_ACTION_REF from VANILLA.V_STEP_INSTANCE "
                  "where INSERT_DT >= SYSDATE - 21 order by INSERT_DT desc")


def get_db_connection():
    """
    Creates a SQLAlchemy engine for Aurora database connection.
    Supports both MySQL and PostgreSQL Aurora.
    """
    # If using SID instead of service_name:
    connection_string = f"oracle+oracledb://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['sid']}"

    engine = create_engine(connection_string, echo=False)
    return engine


def load_data_from_aurora():
    """
    Executes WORKFLOW_QUERY against Aurora database and saves results to data.csv
    """
    try:
        engine = get_db_connection()

        # Execute query and load into DataFrame
        df = pd.read_sql(WORKFLOW_QUERY, engine)

        # Save to CSV
        df.to_csv("data.csv", index=False)

        print(f"Successfully loaded {len(df)} rows from Aurora database to data.csv")
        return True, len(df)

    except Exception as e:
        print(f"Error loading data from Aurora: {str(e)}")
        return False, str(e)


@st.cache_data(ttl=300)  # Cache for 5 minutes
def refresh_data_from_aurora():
    """
    Cached function to refresh data from Aurora database.
    Automatically refreshes every 5 minutes.
    """
    return load_data_from_aurora()



@tool(description="This is a fallback tool. "
                  "This function must be called if no other tool is found to match the request. "
                  "This will return a friendly error message that can be passed to the user."
)
def fallback(user_request: str) -> dict:
    return {"text": "I am sorry, I don't know how to help with that.\n "
                    "I have made record of this request so I can learn to help with that topic in the future!\n\n"
                    "You can always try to ask the question with more detail or context "
                    "and that might help me find the correct tools to help."}


@tool(description="Returns a counts of automated and manual steps.")
def get_count_automated_vs_manual() -> dict:
    print("get_count_automated_vs_manual called")

    try:
        df = pd.read_csv("data.csv")
        
        # Count where is_automated_step is 'Y' vs 'N'
        automated_steps = len(df[df['is_automated_step'] == 'Y'])
        manual_steps = len(df[df['is_automated_step'] == 'N'])

        results = {
            "metric": {"automated_steps": automated_steps, "manual_steps": manual_steps},
            "text": f"Automated steps: {automated_steps}, Manual steps: {manual_steps}"
        }
        print(results)
        return results
    except Exception as e:
        return {"text": f"Error reading data: {str(e)}"}


@tool(description="Returns a count of failed steps.")
def get_count_failed() -> dict:
    print("get_count_failed called")

    try:
        df = pd.read_csv("data.csv")
        
        # Count where type_workflow_action_ref is 'FAILED'
        failed_steps = len(df[df['type_workflow_action_ref'] == 'FAILED'])

        results = {
            "metric": {"failed_steps": failed_steps},
            "text": f"Failed steps: {failed_steps}"
        }
        print(results)
        return results
    except Exception as e:
        return {"text": f"Error reading data: {str(e)}"}


@tool(description="Returns a count of pending steps.")
def get_count_pending() -> dict:
    print("get_count_pending called")

    try:
        df = pd.read_csv("data.csv")
        
        # Count where type_workflow_action_ref is 'PENDING'
        pending_steps = len(df[df['type_workflow_action_ref'] == 'PENDING'])

        results = {
            "metric": {"pending_steps": pending_steps},
            "text": f"Pending steps: {pending_steps}"
        }
        print(results)
        return results
    except Exception as e:
        return {"text": f"Error reading data: {str(e)}"}


@tool(description="Returns a count of skipped steps.")
def get_count_skipped() -> dict:
    print("get_count_skipped called")

    try:
        df = pd.read_csv("data.csv")
        
        # Count where type_workflow_action_ref is 'SKIPPED'
        skipped_steps = len(df[df['type_workflow_action_ref'] == 'SKIPPED'])

        results = {
            "metric": {"skipped_steps": skipped_steps},
            "text": f"Skipped steps: {skipped_steps}"
        }
        return results
    except Exception as e:
        return {"text": f"Error reading data: {str(e)}"}


@tool(description="Returns the top 10 longest running steps.")
def get_longest_running_steps() -> dict:
    print("get_longest_running_steps called")

    try:
        df = pd.read_csv("data.csv")
        
        # Filter out rows with missing or zero elapsed time
        df_filtered = df[df['elapsed'].notna() & (df['elapsed'] > 0)]
        
        # Sort by elapsed time and get top 10
        top_10_df = df_filtered.nlargest(10, 'elapsed')
        
        # Convert to list of dicts
        top_10 = top_10_df[['name', 'elapsed', 'is_automated_step']].to_dict('records')
        
        # Rename keys for clarity
        top_10_formatted = [
            {
                "workflow_name": row['name'],
                "elapsed_minutes": row['elapsed'],
                "automated": row['is_automated_step']
            }
            for row in top_10
        ]
        
        results = {
            "table": top_10_formatted,
            "text": json.dumps(top_10_formatted)
        }
        print(results)
        return results
    except Exception as e:
        return {"text": f"Error reading data: {str(e)}"}


@tool(description="Returns the elapsed time of workflows from start to finish in minutes.")
def get_workflows_durations() -> dict:
    """
    return the elapsed time of workflows from start to finish in minutes
    :return:
    """
    print("get_workflows_durations called")
    
    try:
        df = pd.read_csv("data.csv")
        
        # Filter out rows with missing or zero elapsed time
        df_filtered = df[df['elapsed'].notna() & (df['elapsed'] > 0)]
        
        # Convert to list of dicts
        workflows = df_filtered[['name', 'elapsed', 'is_automated_step']].to_dict('records')
        
        # Rename keys for clarity
        workflows_formatted = [
            {
                "workflow_name": row['name'],
                "elapsed_minutes": row['elapsed'],
                "automated": row['is_automated_step']
            }
            for row in workflows
        ]
        
        results = {
            "table": workflows_formatted,
            "text": json.dumps(workflows_formatted)
        }
        print(results)
        return results
    except Exception as e:
        return {"text": f"Error reading data: {str(e)}"}




@tool(description="Returns the count of completed workflows.")
def get_completed_workflow_infos() -> dict:
    """
    return the count of completed workflows
    :return:
    """
    print("get_completed_workflow_infos called")
    
    try:
        df = pd.read_csv("data.csv")
        
        # Count where type_workflow_action_ref is 'COMPLETE'
        completed_workflows = len(df[df['type_workflow_action_ref'] == 'COMPLETE'])

        results = {
            "metric": {"completed_workflows": completed_workflows},
            "text": f"Completed workflows: {completed_workflows}"
        }
        print(results)
        return results
    except Exception as e:
        return {"text": f"Error reading data: {str(e)}"}


# Add this after the tool definitions and before the Streamlit UI code

# Add to sidebar for manual refresh
with st.sidebar:
    st.markdown("## About")
    st.markdown("This chatbot queries Aurora database for workflow data.")
    st.markdown("---")

    # Add refresh button
    if st.button("🔄 Refresh Data from Aurora"):
        with st.spinner("Fetching data from Aurora database..."):
            success, result = load_data_from_aurora()
            if success:
                st.success(f"✅ Loaded {result} rows from database")
                # Clear cache to force reload
                st.cache_data.clear()
            else:
                st.error(f"❌ Error: {result}")

    # Show last update time
    import os

    if os.path.exists("data.csv"):
        last_modified = os.path.getmtime("data.csv")
        from datetime import datetime

        last_update = datetime.fromtimestamp(last_modified).strftime("%Y-%m-%d %H:%M:%S")
        st.info(f"Data last updated: {last_update}")

    st.markdown("---")
    st.markdown("Made with ❤️ using Streamlit")

# Auto-refresh data on app startup
if "data_loaded" not in st.session_state:
    st.session_state.data_loaded = True
    with st.spinner("Loading initial data from Aurora..."):
        success, result = refresh_data_from_aurora()
        if not success:
            st.warning(f"Could not load data from Aurora: {result}. Using existing data.csv if available.")

tools = [
    fallback,
    get_count_automated_vs_manual,
    get_count_failed,
    get_count_pending,
    get_count_skipped,
    get_longest_running_steps,
    get_workflows_durations,
    get_completed_workflow_infos
]

tool_selector = {
    "fallback": fallback,
    "get_count_automated_vs_manual": get_count_automated_vs_manual,
    "get_count_failed": get_count_failed,
    "get_count_pending": get_count_pending,
    "get_count_skipped": get_count_skipped,
    "get_longest_running_steps": get_longest_running_steps,
    "get_workflows_durations": get_workflows_durations,
    "get_completed_workflow_infos": get_completed_workflow_infos
}

llm = ChatLiteLLM(
    api_base="http://localhost:8000",
    api_key="sk-0dpm_OufkAtISgBy_Esr1g",
    model="openai/llama3.1:8b",
    #model="openai/llama4:latest",
    temperature=0.1
)

agent = llm.bind_tools(tools)

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

with st.chat_message("ai"):
    st.write("Hello! What can I help you with today?")

if prompt := st.chat_input("Ask the bot something"):
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    tool_results = []

    with st.status(":brain: Activating Aurora Brains :brain:", expanded=True) as status:
        # update chain
        messages = [HumanMessage(prompt)]

        # execute the chain to discover the tool(s) to use
        agent_result = agent.invoke(messages)

        for tool_call in agent_result.tool_calls:
            brain_id = tool_call["id"]
            tool_name = tool_call["name"]
            st.write(f":brain: ({brain_id}) discovered tool **'{tool_name}'**")

        # update chain with function runners
        messages.append(agent_result)

        for tool_call in agent_result.tool_calls:
            tool_name = tool_call["name"]
            st.write(f":zap: Tool/function **'{tool_name}'** was called")
            selected_tool = tool_selector[tool_call["name"]]
            tool_result = selected_tool.invoke(tool_call)
            tool_results.append(tool_result)

        status.update(label="Done", state="complete", expanded=True)


    with st.chat_message("ai"):
        for result in tool_results:
            tool_output = result.content
            tool_name = result.name
            tool_call_id = result.tool_call_id
            st.markdown(f"**Tool**: [:blue-background[{tool_name}]]")
            st.markdown(f"**Tool Call ID**: {tool_call_id}")

            try:
                result_data = json.loads(tool_output)

                if "metric" in result_data.keys():
                    st.session_state.messages.append({"role": "ai-metric", "content": result_data["metric"]})
                    for key in result_data["metric"].keys():
                        st.metric(key, result_data["metric"][key], delta=random.uniform(-1, 1))
                    continue

                if "table" in result_data.keys():
                    st.session_state.messages.append({"role": "ai-table", "content": result_data["table"]})
                    st.table(pd.DataFrame.from_dict(result_data["table"]))
                    continue

                if "chart" in result_data.keys():
                    continue

                if "text" in result_data.keys():
                    st.session_state.messages.append({"role": "ai", "content": result_data["text"]})
                    st.write(result_data["text"])



            except ValueError as e:
                st.write(str(e))
