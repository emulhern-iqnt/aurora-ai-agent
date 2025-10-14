from langchain_litellm import ChatLiteLLM
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate

from langgraph.graph import StateGraph
from langgraph.graph import START

from typing_extensions import Annotated
from typing_extensions import TypedDict

import pandas as pd
import os
import urllib.request
from sqlalchemy import create_engine

#Extract data from Aurora DB
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
        df.to_csv("aurora_data.csv", index=False)

        print(f"Successfully loaded {len(df)} rows from Aurora database to aurora_data.csv")
        return True, len(df)

    except Exception as e:
        print(f"Error loading data from Aurora: {str(e)}")
        return False, str(e)

# Download the CSV file if it doesn't exist locally
def get_sales_data():
    csv_path = "s1.csv"
    
    if not os.path.exists(csv_path):
        print("Downloading sales data...")
        # Direct download URL from HuggingFace
        url = "https://huggingface.co/datasets/AbhayBhan/SalesData/resolve/main/s1.csv"
        
        try:
            # Create an SSL context that doesn't verify certificates (use with caution)
            import ssl
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            urllib.request.urlretrieve(url, csv_path)
            print("Download complete!")
        except Exception as e:
            print(f"Download failed: {e}")
            # Fallback: create sample data if download fails
            print("Creating sample data instead...")
            sample_data = {
                'Invoice ID': ['001', '002', '003'],
                'Branch': ['A', 'B', 'C'],
                'City': ['City1', 'City2', 'City3'],
                'Customer type': ['Member', 'Normal', 'Member'],
                'Gender': ['Male', 'Female', 'Male'],
                'Product line': ['Electronics', 'Fashion', 'Food'],
                'Unit price': [100.0, 50.0, 25.0],
                'Quantity': [2, 3, 4],
                'Tax 5%': [10.0, 7.5, 5.0],
                'Total': [210.0, 157.5, 105.0],
                'Date': ['2023-01-01', '2023-01-02', '2023-01-03'],
                'Time': ['10:00', '11:00', '12:00'],
                'Payment': ['Credit card', 'Cash', 'Ewallet'],
                'cogs': [200.0, 150.0, 100.0],
                'gross margin percentage': [5.0, 5.0, 5.0],
                'gross income': [10.0, 7.5, 5.0],
                'Rating': [8.5, 9.0, 7.5]
            }
            df_sample = pd.DataFrame(sample_data)
            df_sample.to_csv(csv_path, index=False)
    
    return pd.read_csv(csv_path)

df = get_sales_data()
df2 = load_data_from_aurora()


class PandasQueryCommandOutput(TypedDict):
    query_command: Annotated[str, "Syntactically correct Pandas DataFrame method call"]


class CorrectionResults(TypedDict):
    new_query_command: Annotated[str, "Syntactically correct Pandas DataFrame method call"]
    new_suggested_prompt: Annotated[str, "A GPT prompt to which is more likely to produce the desired result"]


class State(TypedDict):
    question: str
    query: str
    result: str
    answer: str
    error: str
    retry_count: int


coder_llm = ChatLiteLLM(
    api_base="http://localhost:8000",
    api_key="sk-0dpm_OufkAtISgBy_Esr1g",
    model="openai/qwen2.5-coder:3b",
    temperature=0
)

error_llm = ChatLiteLLM(
    api_base="http://localhost:8000",
    api_key="sk-0dpm_OufkAtISgBy_Esr1g",
    model="openai/codegemma:7b",
    temperature=0
)

# llm = ChatOllama(
#     api_base="http://localhost:8000",
#     api_key="sk-0dpm_OufkAtISgBy_Esr1g",
#     model="llama3.1:8b",
#     temperature=0.8
# )

llm = ChatLiteLLM(
    api_base="http://localhost:8000",
    api_key="sk-0dpm_OufkAtISgBy_Esr1g",
    model="openai/llama3.1:8b",
    #model="openai/llama4:latest",
    temperature=0.1
)

coder_struct_llm = coder_llm.with_structured_output(PandasQueryCommandOutput, include_raw=True)
error_struct_llm = error_llm.with_structured_output(CorrectionResults, include_raw=True)

coder_system_prompt = """
You are a pandas expert tasked with writing DataFrame queries. Use ONLY Python pandas syntax (e.g., df['column'], df.loc, df.groupby). Do NOT generate SQL queries, even if column names resemble SQL table/column patterns. Always use the EXACT column names provided below—do not modify, abbreviate, or alter them (e.g., no replacing spaces with underscores, no removing apostrophes). Copy them directly.

Available columns:
{df_cols}

When writing queries, use pandas methods like df['column'], df.query(), or df.loc[:, 'column']. Never use SQL keywords like SELECT, FROM, WHERE, or JOIN.
"""


def generate_dataframe_command(state: State) -> State:
    query_prompt_template = ChatPromptTemplate(
        [("system", coder_system_prompt), ("user", "Question: {input}")]
    )

    prompt = query_prompt_template.invoke({
        "top_k": 10,
        # "types": df.dtypes,
        "df_cols": "\n".join([f"- '{x}'" for x in df.columns]),
        "input": state["question"],
    })

    response = coder_struct_llm.invoke(prompt)
    parsed_command = response["parsed"]
    metadata = response["raw"].response_metadata

    print(metadata)
    print(f"Structured LLM Generated command '{parsed_command}'")

    return State(query=parsed_command["query_command"])


def execute_dataframe_command(state: State) -> State:
    pandas_command: str = state["query"]

    try:
        result: str = str(eval(pandas_command))
        print(f"EVAL: '{pandas_command}' => Result: {result}")
        return State(result=result, error="")

    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        print(f"EVAL ERROR: '{pandas_command}' => Error: {error_msg}")

        # Initialize retry_count if not present
        current_retry = state.get("retry_count", 0)

        return State(
            error=error_msg,
            retry_count=current_retry + 1
        )


def generate_answer(state: State) -> State:
    # Handle case where execution failed after max retries
    if state.get("error") and not state.get("result"):
        prompt = f"""
        The system attempted to answer the following question but encountered an error:

        Question: {state['question']}
        Attempted Pandas Command: {state.get('query', 'N/A')}
        Error: {state['error']}

        Please provide a helpful response explaining that the query could not be executed 
        and suggest what might have gone wrong or how to rephrase the question.
        """
    else:
        prompt = f"""
        Given the following user question, corresponding pandas dataframe command, 
        and pandas method call result, answer the user question.

        Question: {state['question']}
        Pandas Dataframe Method: {state['query']}
        Pandas Method Call Result: {state['result']}
        """

    annoying_assistant_system_prompt = """
    You are a bubbly assistant that is very excited to happily answer the users questions 
    in a fun way by describing the answer in the cutest way possible.
    """

    statistician_assistant_system_prompt = """
    You are a grizzled old collage statistician. Grumpily provide your answers in arcane old statistician speak.
    """

    french_assistant_system_prompt = """
    Answer the questions with the French language only
    """

    # full_prompt = [
    #     ("system", french_assistant_system_prompt),
    #     ("human", prompt)
    # ]

    full_prompt = [
        ("system", statistician_assistant_system_prompt),
        ("human", prompt)
    ]

    response = llm.invoke(full_prompt)
    print(response.response_metadata)
    print(f"LLM Generated response '{response}'")
    return State(answer=response.content)


def error_correction(state: State) -> State:
    prompt = f"""
    This dataframe has case sensitive column names. It is very important to use the correct column name case when you generate a query.
    These are the column names:
    Column names for reference: 'Invoice ID', 'Branch', 'City', 'Customer type', 'Gender', 'Product line', 'Unit price', 'Quantity', 'Tax 5%', 'Total',
    'Date', 'Time', 'Payment', 'cogs', 'gross margin percentage', 'gross income', 'Rating'

    Initial question: {state['question']}

    Erroneous GPT generated pandas query: {state['query']}

    Errors: {state['error']}

    Please provide the correct pandas query and a suggested better prompt opposed to the originally provided "Initial question".
    """
    response = error_struct_llm.invoke(prompt)
    print(response["raw"].response_metadata)
    return State(query=response["parsed"]["new_query_command"], error="")


def should_retry(state: State) -> str:
    """Routing function to decide whether to retry or proceed"""
    max_retries = 3

    if state.get("error") and state.get("retry_count", 0) < max_retries:
        print(f"Retrying... (Attempt {state.get('retry_count', 0)} of {max_retries})")
        return "retry"
    elif state.get("error"):
        print(f"Max retries ({max_retries}) reached. Proceeding with error.")
        return "generate_answer"
    else:
        return "generate_answer"


# Build the graph with conditional edges
graph_builder = StateGraph(State)

# Add nodes
graph_builder.add_node("generate_dataframe_command", generate_dataframe_command)
graph_builder.add_node("execute_dataframe_command", execute_dataframe_command)
graph_builder.add_node("generate_answer", generate_answer)
graph_builder.add_node("error_correction", error_correction)

# Add edges
graph_builder.add_edge(START, "generate_dataframe_command")
graph_builder.add_edge("generate_dataframe_command", "execute_dataframe_command")
graph_builder.add_edge("error_correction", "execute_dataframe_command")

# Add conditional edge for retry logic
graph_builder.add_conditional_edges(
    "execute_dataframe_command",
    should_retry,
    {
        "retry": "error_correction",
        "generate_answer": "generate_answer"
    }
)

graph = graph_builder.compile()

#Can add
#"We do not know the case of the value 'credit card' so do a case insensitive search"
questions = [
    "average gross income from credit card payment type.",
    "average gross income per gender",
    "5 unique cities",
    "total invoices in branches A and B",
    "total invoices in branches C and D",
]

# questions = [
#     "average gross income per gender",
#     "5 unique cities",
#     "total invoices in branches A and B",
#     "total invoices in branches C and D",
# ]

for question in questions:
    print(f"\n{'=' * 60}")
    print(f"Question: {question}")
    print('=' * 60)

    for mode, message in graph.stream(
            {"question": question, "retry_count": 0, "error": ""},
            stream_mode=["debug", "updates"]
    ):
        if mode == "debug":
            pass
        if mode == "updates":
            if "generate_answer" in message:
                print(f"\n{'=' * 60}")
                print(f"Answer: {message['generate_answer']}")
                print('=' * 60)

            else:
                print(mode, message)
        print()

    print("-----------------------")
    print()
    print()
