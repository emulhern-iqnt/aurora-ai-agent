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
- Use strict MariaDB SQL syntax (e.g., backticks for identifiers, DATETIME for dates).
- Do not invent column names, data types, table names, relationships, or assumptions about the data—stick exactly to the schema provided.
- Products are put into service via workflows (workflow_id), and workflows have several steps (step_instance_id), so group by process_instance_id when answering questions about products, services and orders.
- When asked about durations you must use the elapsed_duration_hours field.
- When asked about SLAs or missed due dates you must use the promised_due_dt and workflow_step_date fields.
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

Note:
Give a brief answer to the question with this provided info.
"""

answer_prompt_template = PromptTemplate(template=answer_prompt, input_variables=["question", "query", "results"])


questions = [
    "What is the average time for 'Emergency Services' products to enabled?",
    "Which 10 products take the longest to fully enable service and how long does it take?",
    # "How many steps missed SLA target last month?",
    # "Which 10 employees had the most workflow steps last month? include number of steps and employee name broken down by week",
    # "number of steps per team name from the last 3 months",
    # "Which of my team members are completing the most/fewest tasks? My team is 'Customer Success'",
    # "Which 3 teams had the best improvement in reduced average duration month-by-month over the last 3 months? broken down by month",
    # "Count of automated vs manual steps completed the last 3 weeks broken down by week",
    # "Are average times for automated steps over the last 3 months (group by month) improving? include the month and average time",
    # "automated vs non-automated steps that failed last month",
    # "Which 3 teams have the highest average duration?",
    # "Which 3 products have the highest average duration?",
    # "Which 3 people have the lowest average duration? please include the team name and average duration",
]


for question in questions:
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

    except Exception as e:
        console.print(sql_query)
        console.print(f"Error: {e}")


    print()
    print("*" * 60)
    print()
    print()
