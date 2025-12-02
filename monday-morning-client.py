from langchain_ollama import ChatOllama
from langchain_litellm import ChatLiteLLM
from langchain_core.prompts import PromptTemplate
from langchain_core.messages import SystemMessage
from langchain_core.messages import HumanMessage
from pydantic import BaseModel
from pydantic import Field
from sqlalchemy import create_engine
from sqlalchemy import text
from pandas import read_sql
from rich.console import Console
from time import time
from os import environ
from AuroraLogging import AuroraLogging
import kpi_explorer


class Query(BaseModel):
    sql_query: str = Field(description="A syntactically correct SQL query")


class Answer(BaseModel):
    answer: str = Field(description="The answer to the question")


SQL_HOST = environ.get("SQL_HOST", "localhost")
SQL_USER = environ.get("SQL_USER", "zero")
SQL_PASS = environ.get("SQL_PASS", "zero")
SQL_READ_DB = environ.get("SQL_READ_DB", "aurora")
mysql_engine = create_engine(f"mysql+pymysql://" + SQL_USER + ":zero@" + SQL_HOST + "/" + SQL_READ_DB)


console = Console()


# sql_llm_base = ChatOllama(model="sqlcoder:15b", temperature=0.1)
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


sql_system_prompt = """
## Instructions:
You are an expert SQL query generator specializing in MariaDB. Your task is to analyze a natural language question and generate a precise, executable SQL SELECT query that answers it, based solely on the provided database schema.

## Key Rules:
- Return only ONE SQL query.
- Use strict MariaDB SQL syntax
- DO NOT invent column names, data types, table names, relationships, or assumptions about the data, use only exactly to the schema provided.

## RULES YOU MUST ALWAYS FOLLOW:
- Only focus on the workflow_steps table when asked specifically about steps or tasks.
- Missed SLAs are any order with days_past_due > 0.
- Questions about durations and elapsed times must use the workflow_elapsed_duration_hours
- Questions that use words like "the most", "the fastest", "the highest", "top performer", etc. do NOT interpret these as a request to return only one row. Always return the full ranked list with counts so the user can see the complete ordering and any ties.
- Even if the question says "who is doing the most", "which team member has the most", or similar, return ALL team members sorted by count descending, never use LIMIT 1 or any LIMIT unless I literally write the words "only the top", "just the first", "limit to 5", etc.
- NEVER add LIMIT, TOP, or any row-limiting clause unless I explicitly ask for a limited number of rows or examples.
- If I ask for a query that returns "all" records, "the full result", or don't specify any limit, return the complete result set without any LIMIT.
- Only use LIMIT when I say things like "show me 10 examples", "sample rows", "first 5", etc.
- The effective_parent_workflow_status field in the workflow_steps table is for informational purposes only and should never be used in any where statements.
- Products are put into service via one or more workflows, and workflows have several steps, so join tables as needed when answering questions about products, services and orders.

Schema:
CREATE TABLE `products` (
  `index` bigint(20) DEFAULT NULL,
  `product_id` bigint(20) DEFAULT NULL,
  `product_name` text DEFAULT NULL,
  `service_name` text DEFAULT NULL,
  `group_product_name` text DEFAULT NULL,
  `parent_product_name` text DEFAULT NULL,
  `is_active` bigint(20) DEFAULT NULL,
  KEY `ix_products_index` (`index`)
)

CREATE TABLE `orders` (
  `index` bigint(20) DEFAULT NULL,
  `order_id` bigint(20) DEFAULT NULL,
  `product_id` bigint(20) DEFAULT NULL,
  `region_name` text DEFAULT NULL,
  `team_manager_name` text DEFAULT NULL,
  `team_name` text DEFAULT NULL,
  `order_status` text DEFAULT NULL,
  `customer_name` text DEFAULT NULL,
  `days_past_due` double DEFAULT NULL,
  `desired_due_date` datetime DEFAULT NULL,
  `create_date` datetime DEFAULT NULL,
  `update_date` datetime DEFAULT NULL,
  KEY `ix_orders_index` (`index`)
)

CREATE TABLE `workflows` (
  `index` bigint(20) DEFAULT NULL,
  `workflow_id` bigint(20) DEFAULT NULL,
  `order_id` double DEFAULT NULL,
  `workflow_name` text DEFAULT NULL,
  `workflow_description` text DEFAULT NULL,
  `workflow_status` text DEFAULT NULL,
  `insert_date` datetime DEFAULT NULL,
  `update_date` datetime DEFAULT NULL,
  `workflow_elapsed_duration_hours` double DEFAULT NULL,
  KEY `ix_workflows_index` (`index`)
)

CREATE TABLE `workflow_steps` (
  `index` bigint(20) DEFAULT NULL,
  `workflow_step_id` bigint(20) DEFAULT NULL,
  `order_id` double DEFAULT NULL,
  `order_item_id` double DEFAULT NULL,
  `workflow_id` bigint(20) DEFAULT NULL,
  `workflow_step_name` text DEFAULT NULL,
  `workflow_step_description` text DEFAULT NULL,
  `effective_parent_workflow_status` text DEFAULT NULL,
  `workflow_step_estimated_duration_days` double DEFAULT NULL,
  `team_name` text DEFAULT NULL,
  `team_id` bigint(20) DEFAULT NULL,
  `team_member` text DEFAULT NULL,
  `workflow_step_due_date` datetime DEFAULT NULL,
  `is_automated_step` bigint(20) DEFAULT NULL,
  `workflow_step_elapsed_duration_hours` double DEFAULT NULL,
  `workflow_step_date` datetime DEFAULT NULL,
  KEY `ix_workflow_steps_index` (`index`)
)

## Status field values are as follows:
### Table workflows have field workflow_status:
- INPROGRESS: In Progress
- COMPLETE: Completed
- PCNCL: Pending Cancel
- CNCL: Cancelled

### Table orders have field order_status:
- PENDING: Pending
- INCMPLT: Incomplete
- CNCL: Cancelled
- PCNCL: Pending Cancel
- CLSD: Completed/Closed


## Table relations:
- `workflow_steps` and `workflows` are related by `workflow_id`
- `workflows` and `orders` are related by `order_id`
- `orders` and `products` are related by `product_id`

## Response format:
Respond only with this exact structure—no additional text, explanations, or chit-chat:
Based on the provided schema and question, here is the MariaDB SQL query:
```sql
"""


question_prompt = """
## Input:
Generate a SQL query that answers the question `{question}`.
"""

question_prompt_template = PromptTemplate(template=question_prompt, input_variables=["question"])


answer_prompt = """
## Input:
The question: {question}

### The database query:
{query}

### The database results:
{results}

### Instructions:
Give a brief answer to the question with this provided info, don't leave out any important details.
"""

answer_prompt_template = PromptTemplate(template=answer_prompt, input_variables=["question", "query", "results"])

try:
    suggestion_df = read_sql(
        text("SELECT question FROM aurora_discovered_kpis ORDER BY RAND() LIMIT 1"),
        mysql_engine
    )
    if len(suggestion_df) > 0:
        suggested_question = suggestion_df.iloc[0]['question']
        console.print(f"\nYou can ask a question like: '{suggested_question}'\n")
except Exception as e:
    # If there's an error fetching suggestions, just continue
    pass

# Remove the questions array and replace with interactive loop
while True:
    # Get user input
    question = console.input("\n[bold cyan]Enter your question (or 'exit' to quit): [/bold cyan]")
    
    # Check if user wants to exit
    if question.lower() in ['exit', 'quit', 'q']:
        console.print("[yellow]Exiting...[/yellow]")
        break
    
    # Skip empty input
    if not question.strip():
        continue

    start_ts = time()

    this_ts = time()
    response = sql_llm_so.invoke([
        SystemMessage(content=sql_system_prompt),
        HumanMessage(content=question_prompt_template.format(question=question))
    ])
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

        # Prepare logging parameters
        user_prompt = question
        generated_query = sql_query
        num_results = len(df)
        user_feedback = False  # or None if you want to leave it undefined
        results_returned_fl = True

        if num_results is None:
           results_returned_fl = False
           num_results = 0

        if num_results == 0:
            results_returned_fl = False

        # Create an instance and call the method
        logger = AuroraLogging()
        logger.log_to_database(user_prompt, generated_query, num_results, user_feedback, results_returned_fl)

    except Exception as e:
        console.print(sql_query)
        console.print(f"Error: {e}")

    print()
    print("*" * 60)
    print()
