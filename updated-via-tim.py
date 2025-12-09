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
from os import environ



class Query(BaseModel):
    sql_query: str = Field(description="A syntactically correct SQL query")


class Answer(BaseModel):
    answer: str = Field(description="The answer to the question")


SQL_HOST = environ.get("SQL_HOST", "localhost")
SQL_USER = environ.get("SQL_USER", "zero")
SQL_PASS = environ.get("SQL_PASS", "zero")
mysql_engine = create_engine(f"mysql+pymysql://" + SQL_USER + ":zero@" + SQL_HOST + "/aurora")


console = Console()


#sql_llm_base = ChatOllama(model="llama3.1:8b", temperature=0.0)
#answer_llm_base = ChatOllama(model="llama3.1:8b", temperature=0.2)


sql_llm_base = ChatLiteLLM(
    api_base="http://localhost:8000",
    api_key=environ.get("LITELLM_API_KEY", "test"),
    model="openai/llama3.1:8b",
    temperature=0.0
)

answer_llm_base = ChatLiteLLM(
    api_base="http://localhost:8000",
    api_key=environ.get("LITELLM_API_KEY", "test"),
    model="openai/llama3.1:8b",
    temperature=0.2
)


sql_llm_so = sql_llm_base.with_structured_output(Query)
answer_llm_so = answer_llm_base.with_structured_output(Answer)


query_prompt = """
### Instructions:
You are an expert SQL query generator specializing in MariaDB. Your task is to analyze a natural language question and generate a precise, executable SQL SELECT query that answers it, based solely on the provided database schema.

Key Rules:
- Return only ONE SQL query.
- When asked about muliple items with plural syntax, ex: "How many products...", "Which steps...", etc. do not limit to a single item. (`limit 1`)
- Use strict MariaDB SQL syntax (e.g., backticks for identifiers, DATETIME for dates).
- Do not invent column names, data types, table names, relationships, or assumptions about the data—stick exactly to the schema provided.
- Products are put into service via workflows (workflow_id), and workflows have several steps (step_instance_id), so group by process_instance_id when answering questions about products, services and orders.
- When asked about durations you must use the elapsed_duration_hours field and include the field in the resultset.
- When asked about SLAs or missed due dates you must use the promised_due_dt and workflow_step_date fields.
- If the question cannot be answered with the given schema (e.g., missing columns or tables), respond with: "Insufficient schema information to answer this query."
- Focus on efficiency: Use appropriate WHERE clauses, JOINs (if implied by schema), GROUP BY, ORDER BY, LIMIT, etc., only as needed.
- Keep the query simple and direct: The result set will be passed to an analysis agent for further refinement, so avoid unnecessary complexity such as multiple UNIONs, subqueries, or over-optimizations unless explicitly required by the question.
- Handle edge cases like NULLs, aggregations (e.g., COUNT, SUM), date filtering (e.g., BETWEEN or DATE functions), and sorting.
- Think step-by-step internally: (1) Identify key entities and required columns from the question. (2) Map them to schema fields. (3) Construct the query logically. (4) Verify it aligns with the question.
- When creating the SQL query, any value used in a 'group by' clause must also be in the select list
- Ensure that when doing joins, ensure that the table name that prepends the column name is the same as the table alias in the FROM clause
- When performing joins, ensure that the table alias used in column references (e.g., ws.column_name) exactly matches the alias defined in the FROM or JOIN clause. For example, if you write "FROM workflow_steps ws", you must use "ws.column_name" not "w.column_name".
- Ensure that if the user asks about products, always grab the product_id from the workflow_steps table when generating the SQL query.
### Input:
Generate a SQL query that answers the question `{question}`.

Schema:
CREATE TABLE `workflow_steps` (
  `index` bigint(20) DEFAULT NULL,
  `workflow_step_id` bigint(20) DEFAULT NULL,
  `order_id` bigint(20) DEFAULT NULL,
  `product_id` bigint(20) DEFAULT NULL,
  `team_manager_name` text DEFAULT NULL,
  `order_item_id` bigint(20) DEFAULT NULL,
  `workflow_id` bigint(20) DEFAULT NULL,
  `workflow_name` text DEFAULT NULL,
  `workflow_step_description` text DEFAULT NULL,
  `status_during_step` text DEFAULT NULL,
  `estimated_duration_days` double DEFAULT NULL,
  `team_name` text DEFAULT NULL,
  `team_id` bigint(20) DEFAULT NULL,
  `employee_name` text DEFAULT NULL,
  `promised_due_dt` datetime DEFAULT NULL,
  `is_automated_step` bigint(20) DEFAULT NULL,
  `elapsed_duration_hours` double DEFAULT NULL,
  `workflow_step_date` datetime DEFAULT NULL,
  KEY `ix_workflow_steps_index` (`index`)
)

CREATE TABLE `products` (
  `index` bigint(20) DEFAULT NULL,
  `product_id` bigint(20) DEFAULT NULL,
  `external_identifier` text DEFAULT NULL,
  `name` text DEFAULT NULL,
  `service_name` text DEFAULT NULL,
  `group_product_name` text DEFAULT NULL,
  `parent_product_name` text DEFAULT NULL,
  KEY `ix_products_index` (`index`)
)


### Table relations:
- `workflow_steps` and `products` are related by `product_id`

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


### Instructions:
With the provided question and database results, generate a brief and concise answer to the question.
If the resultset is empty, respond with "There is not data available to answer this question."
"""

answer_prompt_template = PromptTemplate(template=answer_prompt, input_variables=["question", "query", "results"])


questions = [
    #"Take a count of automated vs manual steps completed, broken down by product id. How many failed?",
    #"which workflow steps names take the longest to complete on average",
    #"trend of manual vs automated steps completed over the last month",
    #"How is my team (team name EMEA Onboarding) doing against their SLAs?"
    #"Which of my team members are completing the most/fewest tasks?",
    #"How long does it take to complete short code orders?",
    #"How is the performance trending over time?",
    #"How many tasks (by product?) are automated vs manual?",
    #"How is that trending over time?",
    #"Which automations have high failure rates?",
    "how long does it take to put a product into service? this might be duration of the overall workflow for a given product possibly by region or country",
]


for question in questions:
    start_ts = time()

    this_ts = time()
    prompt = code_prompt_template.format(question=question)
    response = sql_llm_so.invoke(prompt)
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

    except Exception as e:
        console.print(sql_query)
        console.print(f"Error: {e}")


    print()
    print("*" * 60)
    print()
    print()