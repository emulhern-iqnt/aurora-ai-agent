from langchain_litellm import ChatLiteLLM
from langchain.tools import tool
from langchain_core.messages import HumanMessage
import pandas as pd
import streamlit as st
import json
import random

# Need to run:
# socat TCP-LISTEN:8000,fork,reuseaddr OPENSSL:aigateway.inteliquent.com:443,verify=0
# In order to get this working

WORKFLOW_QUERY = ("select ORDER_ID,STEP_INSTANCE_ID,(((UPDATE_DT - INSERT_DT) * 24) * 60) as ELAPSED,"
                  "INSERT_DT,UPDATE_DT,NAME,IS_AUTOMATED_STEP,TYPE_WORKFLOW_ACTION_REF from VANILLA.V_STEP_INSTANCE "
                  "where INSERT_DT >= SYSDATE - 21 order by INSERT_DT desc")


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

    with open("data.csv", "r") as fh:
        data = fh.read()

    automated_steps = 0
    manual_steps = 0

    lines = data.splitlines()

    for line in lines[1:]:
        items = line.split(",")
        if items[6] == "Y":
            automated_steps += 1
        else:
            manual_steps += 1

    results = {
        "metric": {"automated_steps": automated_steps, "manual_steps": manual_steps},
        "text": f"Automated steps: {automated_steps}, Manual steps: {manual_steps}"
    }
    print(results)
    return results


@tool(description="Returns a count of failed steps.")
def get_count_failed() -> dict:
    print("get_count_failed called")

    with open("data.csv", "r") as fh:
        data = fh.read()

    results = []
    lines = data.splitlines()

    for line in lines[1:]:
        items = line.split(",")
        if items[7] == "FAILED":
            results.append(items[1])

    results = {
        "metric": {"failed_steps": len(results)},
        "text": f"Failed steps: {len(results)}"
    }
    print(results)
    return results


@tool(description="Returns a count of pending steps.")
def get_count_pending() -> dict:
    print("get_count_pending called")

    with open("data.csv", "r") as fh:
        data = fh.read()

    results = []
    lines = data.splitlines()

    for line in lines[1:]:
        items = line.split(",")
        if items[7] == "PENDING":
            results.append(items[1])

    results = {
        "metric": {"pending_steps": len(results)},
        "text": f"Pending steps: {len(results)}"
    }
    print(results)
    return results


@tool(description="Returns a count of skipped steps.")
def get_count_skipped() -> dict:
    print("get_count_skipped called")

    with open("data.csv", "r") as fh:
        data = fh.read()

    results = []
    lines = data.splitlines()

    for line in lines[1:]:
        items = line.split(",")
        if items[7] == "SKIPPED":
            results.append(items[1])

    results = {
        "metric": {"skipped_steps": len(results)},
        "text": f"Skipped steps: {len(results)}"
    }
    return results


@tool(description="Returns the top 10 longest running steps.")
def get_longest_running_steps() -> dict:
    print("get_longest_running_steps called")

    with open("data.csv", "r") as fh:
        data = fh.read()

    results = []
    lines = data.splitlines()

    for line in lines[1:]:
        items = line.split(",")
        if float(items[2]) > 0:
            results.append({
                "workflow_name": items[5],
                "elapsed_minutes": float(items[2]),
                "automated": items[6]
            })

    top_10 = sorted(results, key=lambda x: x["elapsed_minutes"], reverse=True)[:10]
    results = {
        "table": top_10,
        "text": json.dumps(top_10)
    }
    print(results)
    return results


@tool(description="Returns the elapsed time of workflows from start to finish in minutes.")
def get_workflows_durations():
    """
    return the elapsed time of workflows from start to finish in minutes
    :return:
    """
    print("get_workflows_durations called")


@tool(description="Returns the count of completed workflows.")
def get_completed_workflow_infos():
    """
    return the count of completed workflows
    :return:
    """
    print("get_completed_workflow_infos called")
    return "Completed workflows"


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
