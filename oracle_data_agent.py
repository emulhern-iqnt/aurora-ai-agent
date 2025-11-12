from langchain_ollama import ChatOllama
from langchain_litellm import ChatLiteLLM
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel
from pydantic import Field
from sqlalchemy import create_engine
from sqlalchemy import text
from pandas import read_sql
from rich.console import Console
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

console = Console()


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


# Get user input instead of using predefined questions
print("=" * 60)
print("Oracle Data Agent - Ask questions about your workflow data")
print("=" * 60)
print("Type 'exit' or 'quit' to stop\n")

while True:
    # Get user input
    question = input("Enter your question: ").strip()
    
    # Check for exit commands
    if question.lower() in ['exit', 'quit', 'q']:
        print("Goodbye!")
        break
    
    # Skip empty questions
    if not question:
        print("Please enter a valid question.\n")
        continue

    # Show thinking message
    print("\nThinking . . .\n")

    start_ts = time()

    this_ts = time()
    response = sql_llm_so.invoke(code_prompt_template.format(question=question))
    sql_query = response.sql_query

    query_gen_seconds = time() - this_ts

    try:
        this_ts = time()
        df = read_sql(text(sql_query), mysql_engine)
        query_exec_seconds = time() - this_ts

        this_ts = time()
        answer_response = answer_llm_so.invoke(answer_prompt_template.format(
            question=question,
            query=sql_query,
            results=df.to_markdown()
        ))
        answer_gen_seconds = time() - this_ts

        console.print(f"SQL ({query_gen_seconds:.2f}s):\n{sql_query}")
        console.print(f"Dataset ({query_exec_seconds:.2f}s):\n{df.head(20).to_markdown()}")
        console.print()
        console.print(f"Question: {question}")
        console.print(f"Answer ({answer_gen_seconds:.2f}s) ({time() - start_ts:.2f}s):\n{answer_response.answer}")


        user_feedback = None
        if len(df) > 0:
            results_returned_fl = True
            num_results = len(df)
        else:
            results_returned_fl = False
            num_results = 0

        with mysql_write_engine.connect() as log_conn:
            log_query = text("""
                             INSERT INTO prompt_logs (user_prompt, generated_query, num_results, user_feedback, created_at, results_returned_fl)
                             VALUES (:question, :query, :num_results, :user_feedback, NOW(), :results_returned_fl)
                             """)

            log_conn.execute(log_query,
                             {"question": question,
                              "query": sql_query,
                              "num_results": num_results,
                              "user_feedback": user_feedback,
                              "results_returned_fl": results_returned_fl}
                             )
            log_conn.commit()


    except Exception as e:
        console.print(f"[bold red]SQL Query:[/bold red]\n{sql_query}")
        console.print(f"[bold red]Error:[/bold red] {e}")


    print()
    print("*" * 60)
    print()
