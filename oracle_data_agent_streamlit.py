from langchain_litellm import ChatLiteLLM
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel
from pydantic import Field
from sqlalchemy import create_engine
from sqlalchemy import text
from pandas import read_sql
import streamlit as st
from time import time


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

class Answer(BaseModel):
    answer: str = Field(description="The answer to the question")


mysql_engine = create_db_engine_with_retry(f"mysql+pymysql://root:zero@10.44.12.18/aurora_data")
mysql_write_engine = create_db_engine_with_retry(f"mysql+pymysql://root:zero@10.44.12.18/aurora_logging")


sql_llm_base = ChatLiteLLM(
    api_base="http://localhost:8000",
    api_key="sk-0dpm_OufkAtISgBy_Esr1g",
    #model="openai/llama3.1:8b",
    model="openai/llama4:latest",
    temperature=0.1
)
answer_llm_base = ChatLiteLLM(
    api_base="http://localhost:8000",
    api_key="sk-0dpm_OufkAtISgBy_Esr1g",
    #model="openai/llama3.1:8b",
    model="openai/llama4:latest",
    temperature=0.1
)


sql_llm_so = sql_llm_base.with_structured_output(Query)
answer_llm_so = answer_llm_base.with_structured_output(Answer)


query_prompt = """
### Instructions:
You are an expert SQL query generator specializing in MariaDB. Your task is to analyze a natural language question and generate a precise, executab le SQL SELECT query that answers it, based solely on the provided database schema.

Key Rules:
- Return only ONE SQL query.
- Use strict MariaDB SQL syntax (e.g., backticks for identifiers, DATETIME for dates).
- Do not invent column names, data types, table names, relationships, or assumptions about the data—stick exactly to the schema provided.
- If the question cannot be answered with the given schema (e.g., missing columns or tables), respond with: "Insufficient schema information to answer this query."
- Focus on efficiency: Use appropriate WHERE clauses, JOINs (if implied by schema), GROUP BY, ORDER BY, LIMIT, etc., only as needed.
- Keep the query simple and direct: The result set will be passed to an analysis agent for further refinement, so avoid unnecessary complexity such as multiple UNIONs, subqueries, or over-optimizations unless explicitly required by the question.
- Handle edge cases like NULLs, aggregations (e.g., COUNT, SUM), date filtering (e.g., BETWEEN or DATE functions), and sorting.
- Think step-by-step internally: (1) Identify key entities and required columns from the question. (2) Map them to schema fields. (3) Construct the query logically. (4) Verify it aligns with the question.

### Input:
Generate a SQL query that answers the question `{question}`.

Schema:
CREATE TABLE `workflow_steps` (
  `index` bigint(20) DEFAULT NULL,
  `step_instance_id` bigint(20) DEFAULT NULL,
  `step_id` bigint(20) DEFAULT NULL,
  `order_id` bigint(20) DEFAULT NULL,
  `product_id` bigint(20) DEFAULT NULL,
  `service_mgr_name` text DEFAULT NULL,
  `order_item_id` bigint(20) DEFAULT NULL,
  `process_instance_id` bigint(20) DEFAULT NULL,
  `process_name` text DEFAULT NULL,
  `name` text DEFAULT NULL,
  `type_workflow_action_ref` text DEFAULT NULL,
  `estimated_duration` double DEFAULT NULL,
  `team_name` text DEFAULT NULL,
  `team_id` bigint(20) DEFAULT NULL,
  `employee_name` text DEFAULT NULL,
  `due_dt` datetime DEFAULT NULL,
  `is_automated_step` bigint(20) DEFAULT NULL,
  `elapsed_duration_hours` double DEFAULT NULL,
  `update_dt` datetime DEFAULT NULL,
  `action_dt` datetime DEFAULT NULL,
  KEY `ix_workflow_steps_index` (`index`)
)

### Response format:
Respond only with this exact structure—no additional text, explanations, or chit-chat:
Based on the provided schema and question, here is the MariaDB SQL query:
```sql
"""

code_prompt_template = PromptTemplate(template=query_prompt, input_variables=["question"])


answer_prompt = """

### Input:
The question: {question}

The database query:
{query}

The database results:
{results}

Note:
Give a brief answer to the question with this provided info.
"""

answer_prompt_template = PromptTemplate(template=answer_prompt, input_variables=["question", "query", "results"])



st.set_page_config(page_title="Oracle Data Agent", page_icon="🔍", layout="wide")
st.title("🔍 Oracle Data Agent")
st.markdown("Ask questions about your workflow data in natural language")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "feedback_states" not in st.session_state:
    st.session_state.feedback_states = {}

with st.sidebar:
    st.markdown("## About")
    st.markdown("This assistant queries your workflow database using natural language.")
    st.markdown("---")



# Show a random suggested question
try:
    suggestion_df = read_sql(
        text("SELECT question FROM aurora_discovered_kpis ORDER BY RAND() LIMIT 1"),
        mysql_engine
    )
    if len(suggestion_df) > 0:
        st.markdown("### 💡 Example Question")
        st.info(suggestion_df.iloc[0]['question'])
except Exception as e:
    pass

st.markdown("---")
st.markdown("Made with ❤️ using Streamlit")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["role"] == "assistant":
            if message["content"]["type"] == "query":
                st.markdown(f"**Generated SQL Query:**")
                st.code(message["content"]["data"], language="sql")
            elif message["content"]["type"] == "answer":
                st.markdown(f"**Answer:**")
                st.markdown(message["content"]["data"])
            elif message["content"]["type"] == "df":
                st.markdown(f"**Query Results:** ({message['content']['num_results']} rows)")
                st.dataframe(message["content"]["data"], use_container_width=True)
            elif message["content"]["type"] == "error":
                st.error(message["content"]["data"])
            else:
                st.markdown(message["content"])

human_message = st.chat_input("Ask a question about the workflow data...")
if human_message:
    # Display user message
    with st.chat_message("user"):
        st.markdown(human_message)
        st.session_state.messages.append({"role": "user", "content": human_message})

df = None
sql_query = None
answer_text = None

with st.status("Processing your question...", expanded=True) as status:
    try:
        # Generate SQL query
        st.write("🧠 Generating SQL query...")
        start_ts = time()

        this_ts = time()
        response = sql_llm_so.invoke(code_prompt_template.format(question=human_message))
        sql_query = response.sql_query
        query_gen_seconds = time() - this_ts

        st.markdown(f"**Generated SQL Query:**")
        st.code(sql_query, language="sql")
        st.write(f"✅ Query generated in {query_gen_seconds:.2f}s")

        # Execute query
        st.write("🔍 Executing query...")
        this_ts = time()
        df = read_sql(text(sql_query), mysql_engine)
        query_exec_seconds = time() - this_ts
        st.write(f"✅ Query executed in {query_exec_seconds:.2f}s ({len(df)} rows)")

        # Generate answer
        st.write("💬 Generating answer...")
        this_ts = time()
        answer_response = answer_llm_so.invoke(answer_prompt_template.format(
            question=human_message,
            query=sql_query,
            results=df.to_markdown()
        ))
        answer_text = answer_response.answer
        answer_gen_seconds = time() - this_ts
        total_time = time() - start_ts
        st.write(f"✅ Answer generated in {answer_gen_seconds:.2f}s (Total: {total_time:.2f}s)")

        status.update(label="Complete!", state="complete", expanded=False)

    except Exception as e:
        status.update(label="Error occurred", state="error", expanded=True)
        st.error(f"Error: {str(e)}")

        # Log error
        with st.chat_message("assistant"):
            st.session_state.messages.append({"role": "assistant", "content": {
                "type": "error",
                "data": f"Error: {str(e)}\n\nGenerated SQL: {sql_query if sql_query else 'N/A'}"
            }})

# Display results if successful
if df is not None and sql_query and answer_text:
    with st.chat_message("assistant"):
        # Store query
        st.session_state.messages.append({"role": "assistant", "content": {
            "type": "query",
            "data": sql_query
        }})


        # Store and display answer
        st.session_state.messages.append({"role": "assistant", "content": {
            "type": "answer",
            "data": answer_text
        }})


        # Store and display dataframe
        num_results = len(df)
        st.session_state.messages.append({"role": "assistant", "content": {
            "type": "df",
            "data": df,
            "num_results": num_results
        }})
        st.markdown(f"**Query Results:** ({num_results} rows)")
        st.dataframe(df, use_container_width=True)

        st.markdown(f"**Answer:**")
        st.markdown(answer_text)

        # Feedback widget
        feedback_key = f"feedback_msg_{len(st.session_state.messages) - 1}"

        st.markdown("---")
        st.markdown("**Does this answer seem reasonable to you?**")
        user_feedback_raw = st.feedback("thumbs", key=feedback_key)

        # Convert feedback to boolean and log
        if user_feedback_raw is not None:
            user_feedback = True if user_feedback_raw == 1 else False
            st.session_state.feedback_states[feedback_key] = user_feedback

            # Determine flags
            results_returned_fl = num_results > 0

            # Log to database
            try:
                with mysql_write_engine.connect() as log_conn:
                    log_query = text("""
                                     INSERT INTO prompt_logs (user_prompt, generated_query, num_results, user_feedback,
                                                              created_at, results_returned_fl)
                                     VALUES (:question, :query, :num_results, :user_feedback, NOW(),
                                             :results_returned_fl)
                                     """)
                    log_conn.execute(log_query, {
                        "question": human_message,
                        "query": sql_query,
                        "num_results": num_results,
                        "user_feedback": user_feedback,
                        "results_returned_fl": results_returned_fl
                    })
                    log_conn.commit()
                st.success("✅ Feedback recorded!" if user_feedback else "👎 Feedback recorded. We'll work to improve!")
            except Exception as log_error:
                st.warning(f"Failed to log feedback: {log_error}")
        elif feedback_key in st.session_state.feedback_states:
            user_feedback = st.session_state.feedback_states[feedback_key]
            st.info(f"Previous feedback: {'👍 Positive' if user_feedback else '👎 Negative'}")


