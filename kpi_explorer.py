from langchain_ollama import ChatOllama
from langchain_litellm import ChatLiteLLM
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel
from pydantic import Field
from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy import insert
from pandas import read_sql
from rich.console import Console
from time import time



class DatabaseQuestion(BaseModel):
    question: str = Field(description="A natural language question about the database intended for exploring new KPIs")


class Query(BaseModel):
    sql_query: str = Field(description="A syntactically correct SQL query")


class Answer(BaseModel):
    answer: str = Field(description="The answer to the question")

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


mysql_engine = create_db_engine_with_retry(f"mysql+pymysql://root:zero@10.44.12.18/aurora_data")


console = Console()


sql_llm_base = ChatLiteLLM(
    api_base="http://localhost:8000",
    api_key="sk-0dpm_OufkAtISgBy_Esr1g",
    model="openai/llama3.1:8b",
    #model="openai/llama4:latest",
    temperature=0.1
)
answer_llm_base = ChatLiteLLM(
    api_base="http://localhost:8000",
    api_key="sk-0dpm_OufkAtISgBy_Esr1g",
    model="openai/llama3.1:8b",
    #model="openai/llama4:latest",
    temperature=0.1
)
explorer_llm_base = ChatLiteLLM(
    api_base="http://localhost:8000",
    api_key="sk-0dpm_OufkAtISgBy_Esr1g",
    model="openai/llama3.1:8b",
    #model="openai/llama4:latest",
    temperature=0.1
)


sql_llm_so = sql_llm_base.with_structured_output(Query)
answer_llm_so = answer_llm_base.with_structured_output(Answer)
explorer_llm_so = explorer_llm_base.with_structured_output(DatabaseQuestion)


workflows_schema = """
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
"""
sample_data = read_sql("SELECT * FROM workflow_steps ORDER BY RAND() LIMIT 10", mysql_engine).to_markdown()



query_prompt = """
### Instructions:
You are an expert SQL query generator specializing in MariaDB. Your task is to analyze a natural language question and generate a precise, executable SQL SELECT query that answers it, based solely on the provided database schema.

Key Rules:
- Return only ONE SQL query.
- Use strict MariaDB SQL syntax (e.g., backticks for identifiers, DATETIME for dates).
- Do not invent column names, data types, table names, relationships, or assumptions about the data—stick exactly to the schema provided.
- When asked about SLAs or missed due dates you must use the promised_due_dt and workflow_step_date fields.
- If the question cannot be answered with the given schema (e.g., missing columns or tables), respond with: "Insufficient schema information to answer this query."
- Focus on efficiency: Use appropriate WHERE clauses, JOINs (if implied by schema), GROUP BY, ORDER BY, LIMIT, etc., only as needed.
- Keep the query simple and direct: The result set will be passed to an analysis agent for further refinement, so avoid unnecessary complexity such as multiple UNIONs, subqueries, or over-optimizations unless explicitly required by the question.
- Handle edge cases like NULLs, aggregations (e.g., COUNT, SUM), date filtering (e.g., BETWEEN or DATE functions), and sorting.
- Think step-by-step internally: (1) Identify key entities and required columns from the question. (2) Map them to schema fields. (3) Construct the query logically. (4) Verify it aligns with the question.

### Input:
Generate a SQL query that answers the question `{question}`.

Schema:
{schema}

### Response format:
Respond only with this exact structure—no additional text, explanations, or chit-chat:
Based on the provided schema and question, here is the MariaDB SQL query:
```sql
"""

code_prompt_template = PromptTemplate(template=query_prompt, input_variables=["schema", "question"])


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


question_prompt = """
### Improved Prompt for Exploratory Question Generation

You are an expert data explorer specializing in uncovering KPIs, metrics, and actionable business insights from databases. Your role is to generate **exactly one** novel, natural-language question that probes the database for valuable discoveries, such as trends, correlations, anomalies, summaries, or comparisons that could inform business decisions. Prioritize diversity to ensure broad coverage of the schema.

### Inputs:
- **Database Schema**: {schema} – This describes the tables, columns, data types, relationships, and any constraints.
- **Sample Data**: {data} – A subset of rows from key tables to understand data patterns, distributions, and quality.
- **Previous Questions**: {old_questions} – A comprehensive list of already-generated questions. **Critically analyze this list to avoid any semantic overlap.** Do not regenerate questions that cover similar ground, such as:
  - The same or overlapping KPIs/metrics (e.g., if "average revenue" was asked, avoid variations like "mean sales").
  - Identical or near-identical groupings/segmentations (e.g., by region, time period, or user type).
  - Repeated timeframes (e.g., if last year was covered, shift to quarterly or predictive periods).
  - Comparable joins or entity combinations (e.g., if customer-product trends were explored, pivot to supplier-ops or risk factors).

### Guidelines for Generating the Question:
- **Novelty First**: Before brainstorming, categorize previous questions by theme (e.g., revenue trends, customer segmentation, operational efficiency). Explicitly target an underrepresented category or a fresh combination of schema elements. If the list exhausts obvious angles, invent a creative, hypothesis-driven probe (e.g., "How do external factors like seasonality correlate with churn rates?").
- Craft one question only, phrased in clear, natural English as if asking a colleague (e.g., "Which product categories show the highest variance in delivery times across regions, and why might that indicate supply chain issues?").
- Focus on high-value exploration: Aggregations (sums, averages, counts, percentiles), trends (YoY growth, seasonal patterns), segmentations (by demographics, cohorts), ratios (efficiency scores, retention rates), outliers (top/bottom performers), or cross-entity correlations (e.g., marketing spend vs. acquisition cost).
- Ensure SQL executability: Implicitly reference schema elements without naming tables/columns explicitly. Assume the NL2SQL agent handles translation.
- Promote diversity: Alternate between quantitative (metrics/KPIs) and qualitative angles (e.g., "What patterns in employee turnover align with peak workload periods?"). Vary scope: macro (overall summaries) vs. micro (drill-downs), historical vs. forward-looking.
- Keep it concise (1 sentence max) but specific for accurate NL2SQL translation.
- Business Impact: Every question must tie to decisions, like optimization, risk mitigation, or opportunity identification.

### Output Format:
Respond with **only** the single natural-language question, enclosed in triple backticks for clarity:
```
Your generated question here.
```
If exhaustive analysis shows no viable new question without duplication (e.g., schema fully probed), output exactly: "Exhausted exploratory angles – suggest schema expansion." Do not explain or add text."""

question_prompt_template = PromptTemplate(template=question_prompt, input_variables=["schema", "data", "old_questions"])


questions = 0

new_kpis_count = 0
while questions <= 10:
    fetch_questions = read_sql("SELECT question FROM aurora_discovered_kpis", mysql_engine)
    old_questions = fetch_questions.question.tolist()
    old_questions_str = "\n".join([f"- {question}" for question in old_questions])
    if old_questions_str == "":
        old_questions_str = "No previous questions."
    start_ts = time()

    this_ts = time()
    response = explorer_llm_so.invoke(question_prompt_template.format(
        schema=workflows_schema,
        data=sample_data,
        old_questions=old_questions_str
    ))
    question = response.question
    question_gen_seconds = time() - this_ts

    this_ts = time()
    response = sql_llm_so.invoke(code_prompt_template.format(schema=workflows_schema, question=question))
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
        answer = answer_response.answer
        answer_gen_seconds = time() - this_ts

        console.print(f"SQL ({query_gen_seconds:.2f}s):\n{sql_query}")
        console.print(f"Dataset ({query_exec_seconds:.2f}s):\n{df.head(20).to_markdown()}")
        console.print()
        console.print(f"Question ({question_gen_seconds:.2f}s): {question}")
        console.print(f"Answer ({answer_gen_seconds:.2f}s) ({time() - start_ts:.2f}s):\n{answer}")
        questions += 1

        check_query = read_sql("SELECT distinct(sql_query) FROM aurora_discovered_kpis", mysql_engine)

        if sql_query in check_query.sql_query.tolist():
            console.print("Duplicate query found, skipping...")
            continue

        with mysql_engine.connect() as conn:
            query = text("INSERT INTO aurora_discovered_kpis (question,sql_query,answer,question_gen_time_seconds,"
                         "query_gen_time_seconds,answer_gen_time_seconds) VALUES (:question,:sql_query,:answer,"
                         ":question_gen_time_seconds,:query_gen_time_seconds,:answer_gen_time_seconds)")
            conn.execute(query, {
                "question": question,
                "sql_query": sql_query,
                "answer": answer,
                "question_gen_time_seconds": question_gen_seconds,
                "query_gen_time_seconds": query_gen_seconds,
                "answer_gen_time_seconds": answer_gen_seconds
            })
            conn.commit()
            console.print("Query saved to database.")
            new_kpis_count += 1

    except Exception as e:
        console.print(sql_query)
        console.print(f"Error: {e}")


    print()
    print("*" * 60)
    print()
    print()
console.print(f"New KPIs generated: {new_kpis_count}")
