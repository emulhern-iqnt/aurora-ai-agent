from langchain_ollama import ChatOllama
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel
from pydantic import Field
from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.sql.elements import TextClause
from pandas import read_sql
import streamlit as st



class Query(BaseModel):
    sql_query: str = Field(description="A syntactically correct SQL query")


schema_items = []
mysql_engine = create_engine(f"mysql+pymysql://zero:zero@localhost/aurora")


with mysql_engine.connect() as connection:
    query: TextClause = text("SHOW TABLES")
    tables = connection.execute(query)

    for table, in tables:
        schema_items.append(f"\n**{table}**")
        table_query: TextClause = text(f"DESCRIBE {table}")
        columns = connection.execute(table_query)

        for column, data_type, *_ in columns:
            schema_items.append(f"- {column}: {data_type}")

schema = "\n".join(schema_items)


sql_llm_base = ChatOllama(model="llama3.1:8b", temperature=0.1)
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
        response = sql_llm_so.invoke(code_prompt_template.format(schema=schema, question=human_message))
        st.markdown(f"```sql\n{response.sql_query}\n```")

        try:
            query = response.sql_query
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

            sentiment_mapping = [":material/thumb_down:", ":material/thumb_up:"]
            selected = st.feedback("thumbs")
            if selected is not None:
                st.markdown(f"You selected: {sentiment_mapping[selected]}")

    else:
        with st.chat_message("assistant"):
            st.error(f"Whoopsie: {response}")