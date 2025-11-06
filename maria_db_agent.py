import os

from langchain_ollama import ChatOllama
from langchain_litellm import ChatLiteLLM
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel
from pydantic import Field
from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.sql.elements import TextClause
from pandas import read_sql
import streamlit as st
import time

# Need to run:
# socat TCP-LISTEN:8000,fork,reuseaddr OPENSSL:aigateway.inteliquent.com:443,verify=0
# In order to get this working

class Query(BaseModel):
    sql_query: str = Field(description="A syntactically correct SQL query")

def create_db_engine_with_retry(connection_string, max_retries=5, retry_delay=2):
    """Create database engine with retry logic"""
    for attempt in range(max_retries):
        try:
            engine = create_engine(connection_string)
            # Test the connection
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return engine
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"Database connection attempt {attempt + 1} failed: {e}. Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
            else:
                raise Exception(f"Failed to connect to database after {max_retries} attempts: {e}")

mysql_schema_items = []
postgres_schema_items = []

try:
    mysql_engine = create_db_engine_with_retry(f"mysql+pymysql://root:zero@10.44.12.18/vitel")
    mysql_write_engine = create_db_engine_with_retry(f"mysql+pymysql://root:zero@10.44.12.18/aurora_logging")
    postgres_engine = create_db_engine_with_retry(f"postgresql+psycopg2://readonly:r3adownly@10.44.12.18:5432/vitel_db")
    
except Exception as e:
    st.error(f"Failed to initialize database connections: {e}")
    st.stop()

with postgres_engine.connect() as connection:
    query: TextClause = text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'billing' AND "
                             "table_type = 'BASE TABLE' ORDER BY table_name;")
    tables = connection.execute(query)

    for table, in tables:
        postgres_schema_items.append(f"\n**{table}**")
        table_query: TextClause = text(f"SELECT column_name, data_type, is_nullable, column_default "
                                       f"FROM information_schema.columns where table_schema = 'billing' and table_name = '{table}'")
        columns = connection.execute(table_query)

        for column, data_type, *_ in columns:
            postgres_schema_items.append(f"- {column}: {data_type}")

postgres_schema = "\n".join(postgres_schema_items)


with mysql_engine.connect() as connection:
    query: TextClause = text("SHOW TABLES")
    tables = connection.execute(query)

    for table, in tables:
        mysql_schema_items.append(f"\n**{table}**")
        table_query: TextClause = text(f"DESCRIBE {table}")

        columns = connection.execute(table_query)

        for column, data_type, *_ in columns:
            mysql_schema_items.append(f"- {column}: {data_type}")

mysql_schema = "\n".join(mysql_schema_items)



#sql_llm_base = ChatOllama(model="llama3.1:8b", temperature=0.1)
sql_llm_base = ChatLiteLLM(
    api_base="http://localhost:8000",
    api_key="sk-0dpm_OufkAtISgBy_Esr1g",
    #model="openai/llama3.1:8b",
    model="openai/llama4:latest",
    temperature=0.1
)

sql_llm_so = sql_llm_base.with_structured_output(Query)


query_prompt = """
You are an expert MariaDB SQL query generator for a relational database. Your task is to translate natural language questions into valid, efficient SQL SELECT queries (using MariaDB/MySQL-compatible syntax). Do not generate INSERT, UPDATE, DELETE, or any other non-SELECT statements—stick to read-only queries. Always assume the database is case-sensitive for table/column names, and use single quotes for string literals.

**CRITICAL RULES:**
- ONLY use columns and tables *exactly* as named in the schema below. Do not invent, assume, or hallucinate any column names, data types, or relationships.
- Before writing the query, silently reason: (1) Map each entity in the question (e.g., 'status') to the *exact* table and column from the schema. (2) Confirm all columns exist in the chosen table(s). (3) If a column is missing, the query cannot proceed—output 'SELECT "Schema error: Column not found" AS result;' instead.
- Do not perform joins unless necessary (e.g., only if the question requires data from multiple tables).
- Use appropriate WHERE, GROUP BY, ORDER BY, and LIMIT for efficiency.
- For date/time intervals, use MariaDB syntax: e.g., `DATE_SUB(CURRENT_DATE, INTERVAL 1 MONTH)` or `CURRENT_DATE - INTERVAL 1 MONTH` (no quotes around the interval value like '1 MONTH').

**SCHEMA**:
{schema}

**EXAMPLE 1:** Question: "Count workflows by order_id."
Reasoning (internal): 'workflows' → aurora_workflows_all; 'order_id' exists there.
Query: SELECT COUNT(*) FROM aurora_workflows_all GROUP BY order_id;

**EXAMPLE 2:** Question: "List steps with status 'COMPLETE'."
Reasoning (internal): 'steps' and 'status' → aurora_steps_all; status_during_step matches.
Query: SELECT * FROM aurora_steps_all WHERE status_during_step = 'COMPLETE';

**EXAMPLE 3:** Question: "Show records from the last month."
Reasoning (internal): Use CURRENT_DATE and INTERVAL for MariaDB date filtering.
Query: SELECT * FROM aurora_workflows_all WHERE created_date >= CURRENT_DATE - INTERVAL 1 MONTH;

User question: {question}
Generate exactly one SQL query that directly answers the question. If ambiguous, make a reasonable assumption based on the schema and prioritize the most straightforward interpretation.

Output only the SQL query enclosed in ```sql ... ``` block. Do not add explanations, comments, or additional text.
"""

code_prompt_template = PromptTemplate(
    template=query_prompt,
    input_variables=["schema", "question"]
)


questions = [
    "What are the top 10 steps (ids and names and average) with longest average durations?",
    "10 non automated workflow steps with longest average durations, include step name and average duration",
    "count of automated vs manual steps completed, how many failed?",
    "which 3 steps (ids and names) take the longest to complete?",
    "count of distinct automated values over the last 2 months broken down by week"
]


if "messages" not in st.session_state:
    st.session_state.messages = []
if "feedback" not in st.session_state:
    st.session_state.feedback = {}
else:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message["role"] == "assistant":
                if "query" in message["content"]["type"]:
                    st.markdown(f"```sql\n{message['content']['data']}\n```")

                elif "df" in message["content"]["type"]:
                    st.dataframe(message['content']['data'].head(50))

                else:
                    st.markdown(message["content"])
            else:
                st.markdown(message["content"])

if "feedback_states" not in st.session_state:
    st.session_state.feedback_states = {}


human_message = st.chat_input("Ask a question about the data")

if human_message:
    with st.chat_message("user"):
        st.markdown(human_message)
    st.session_state.messages.append({"role": "user", "content": human_message})


    df = None
    error = "Undefined"

    with st.status("Doing stuff...", expanded=True) as status:
        st.write("Generating SQL query...")
        status.update(label="Generating SQL query...", state="running", expanded=True)
        # breaking here
        if os.environ.get("DB_SOURCE") == "postgres":
            schema = postgres_schema
        else:
            schema = mysql_schema
        response = sql_llm_so.invoke(code_prompt_template.format(schema=schema, question=human_message))
        st.markdown(f"```sql\n{response.sql_query}\n```")

        try:
            query = response.sql_query
            if os.environ.get("DB_SOURCE") == "postgres":
                df = read_sql(query, postgres_engine)
            else:
                df = read_sql(query, mysql_engine)

        except Exception as e:
            error = str(e)
            st.error(f"Error: {e} -- {response}")

        status.update(label="Done", state="complete", expanded=True)

    if not df is None:
        with st.chat_message("assistant"):
            st.session_state.messages.append({"role": "assistant", "content": {
                "type": "query",
                "data": query
            }})

            st.session_state.messages.append({"role": "assistant", "content": {
                "type": "df",
                "data": df
            }})

            st.dataframe(df.head(50))
            num_results = len(df)

            # Create feedback widget for the new response
            feedback_key = f"feedback_msg_{len(st.session_state.messages) - 1}"
            user_feedback_raw = st.feedback("thumbs", key=feedback_key)
            
            # Convert feedback to 0 or 1
            if user_feedback_raw is not None:
                user_feedback = 1 if user_feedback_raw == 1 else 0
                st.session_state.feedback_states[feedback_key] = user_feedback
                st.write(f"Thank you for your feedback! (Value: {user_feedback})")
            elif feedback_key in st.session_state.feedback_states:
                user_feedback = st.session_state.feedback_states[feedback_key]
                st.write(f"Previous feedback: {user_feedback}")
            else:
                user_feedback = None

    else:
        with st.chat_message("assistant"):
            st.error(f"Whoopsie: {response}")

    # Log the prompt, query, number of results, and user feedback to the database
    try:
        #if sentiment_mapping[selected] == ":material/thumb_up:":
        #    user_feedback = 1
        #else:
        #user_feedback = 0
       
        with mysql_write_engine.connect() as log_conn:
            log_query = text("""
                             INSERT INTO prompt_logs (user_prompt, generated_query, num_results, user_feedback, created_at)
                             VALUES (:prompt, :query, :num_results, :user_feedback, NOW())
                             """)
            log_conn.execute(log_query, {"prompt": human_message, "query": response.sql_query, "num_results": num_results, "user_feedback": user_feedback})
            log_conn.commit()
    except Exception as log_error:
        st.warning(f"Failed to log query: {log_error}")