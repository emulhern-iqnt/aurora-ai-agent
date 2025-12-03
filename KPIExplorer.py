from langchain_ollama import ChatOllama
from langchain_litellm import ChatLiteLLM
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text
from pandas import read_sql
from rich.console import Console
from time import time, sleep
from os import environ


class DatabaseQuestion(BaseModel):
    question: str = Field(description="A natural language question about the database intended for exploring new KPIs")


class Query(BaseModel):
    sql_query: str = Field(description="A syntactically correct SQL query")


class Answer(BaseModel):
    answer: str = Field(description="The answer to the question")


class KPIExplorer:
    def __init__(self, mysql_engine=None, console=None):
        """
        Initialize the KPI Explorer

        Args:
            mysql_engine: Optional SQLAlchemy engine. If None, will create from env vars
            console: Optional Rich Console. If None, will create a new one
        """
        # Setup database connection
        if mysql_engine is None:
            SQL_HOST = environ.get("SQL_HOST", "localhost")
            SQL_USER = environ.get("SQL_USER", "zero")
            SQL_PASS = environ.get("SQL_PASS", "zero")
            self.mysql_engine = create_engine(f"mysql+pymysql://{SQL_USER}:zero@{SQL_HOST}/aurora_data")
        else:
            self.mysql_engine = mysql_engine

        # Setup console
        self.console = console if console is not None else Console()

        # Setup LLMs
        self.sql_llm_base = ChatLiteLLM(
            api_base="http://localhost:8000",
            api_key=environ.get("LITELLM_API_KEY", "test"),
            model="openai/llama3.1:8b",
            temperature=0.0
        )

        self.answer_llm_base = ChatLiteLLM(
            api_base="http://localhost:8000",
            api_key=environ.get("LITELLM_API_KEY", "test"),
            model="openai/llama3.1:8b",
            temperature=0.2
        )

        self.explorer_llm_base = ChatLiteLLM(
            api_base="http://localhost:8000",
            api_key=environ.get("LITELLM_API_KEY", "test"),
            model="openai/llama3.1:8b",
            temperature=0.7
        )

        # Setup structured outputs
        self.sql_llm_so = self.sql_llm_base.with_structured_output(Query)
        self.answer_llm_so = self.answer_llm_base.with_structured_output(Answer)
        self.explorer_llm_so = self.explorer_llm_base.with_structured_output(DatabaseQuestion)

        # Setup prompts
        self._setup_prompts()

    def _setup_prompts(self):
        """Setup all prompt templates"""
        self.query_prompt = """
        ### Instructions:
        You are an expert SQL query generator specializing in MariaDB. Generate a precise, executable SQL SELECT query based on the provided schema.
        
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
        
        ### Response format:
        Based on the provided schema and question, here is the MariaDB SQL query:
`       ``sql"""

        self.code_prompt_template = PromptTemplate(
            template=self.query_prompt,
            input_variables=["question"]
        )

        self.answer_prompt = """### Input:
        The question: {question}

        The database query:
        {query}

        The database results:
        {results}

        Note:
        Give a brief answer to the question with this provided info."""

        self.answer_prompt_template = PromptTemplate(
            template=self.answer_prompt,
            input_variables=["question", "query", "results"]
        )

        # Define schema for question generation
        self.workflows_schema = """
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
        """
        
        self.sample_data = read_sql("SELECT * FROM workflow_steps ORDER BY RAND() LIMIT 10", self.mysql_engine).to_markdown()

        self.question_prompt = """
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

        self.question_prompt_template = PromptTemplate(
            template=self.question_prompt,
            input_variables=["schema", "data", "old_questions"]
        )

    def generate_questions(self, count=5, old_questions=None):
        self.console.print("Generating questions...")
        """
        Generate new KPI exploration questions

        Args:
            count: Number of questions to generate
            old_questions: List of previous questions to avoid duplicates

        Returns:
            List of generated questions
        """
        old_questions_str = "\n".join(old_questions) if old_questions else "None"

        questions = []
        for _ in range(count):
            response = self.explorer_llm_so.invoke(
                self.question_prompt_template.format(
                    schema=self.workflows_schema,
                    data=self.sample_data,
                    old_questions=old_questions_str
                )
            )
            questions.append(response.question)
            old_questions_str += f"\n{response.question}"
        self.console.print("")
        return questions

    def explore_question(self, question, show_output=True):
        """
        Explore a single question by generating SQL, executing it, and generating an answer

        Args:
            question: The natural language question to explore
            show_output: Whether to print output to console

        Returns:
            Dictionary with question, sql_query, dataframe, answer, and timing info
        """
        self.console.print(f"Question: {question}")
        start_ts = time()
        result = {
            'question': question,
            'success': False,
            'error': None
        }

        try:
            # Generate SQL query
            this_ts = time()
            response = self.sql_llm_so.invoke(
                self.code_prompt_template.format(question=question)
            )
            sql_query = response.sql_query
            result['sql_query'] = sql_query
            result['query_gen_seconds'] = time() - this_ts

            # Execute query
            this_ts = time()
            df = read_sql(text(sql_query), self.mysql_engine)
            result['dataframe'] = df
            result['query_exec_seconds'] = time() - this_ts

            # Generate answer
            this_ts = time()
            answer_response = self.answer_llm_so.invoke(
                self.answer_prompt_template.format(
                    question=question,
                    query=sql_query,
                    results=df.to_markdown()
                )
            )
            result['answer'] = answer_response.answer
            result['answer_gen_seconds'] = time() - this_ts
            result['total_seconds'] = time() - start_ts
            result['success'] = True

            if show_output:
                self.console.print(f"\n[bold cyan]Question:[/bold cyan] {question}")
                self.console.print(f"[bold green]SQL[/bold green] ({result['query_gen_seconds']:.2f}s):\n{sql_query}")
                self.console.print(
                    f"[bold yellow]Dataset[/bold yellow] ({result['query_exec_seconds']:.2f}s):\n{df.head(20).to_markdown()}")
                self.console.print(
                    f"[bold magenta]Answer[/bold magenta] ({result['answer_gen_seconds']:.2f}s):\n{result['answer']}")
                self.console.print(f"[dim]Total time: {result['total_seconds']:.2f}s[/dim]")
                self.console.print("\n" + "*" * 60 + "\n")

        except Exception as e:
            result['error'] = str(e)
            if show_output:
                self.console.print("")
                self.console.print(f"[bold red]Error:[/bold red] {e}")
                self.console.print("-"*60)
                self.console.print(f"SQL: {result['sql_query']}")
                if 'sql_query' in result:
                    self.console.print("*"*60)

        return result

    def explore_multiple(self, questions, show_output=True):
        """
        Explore multiple questions

        Args:
            questions: List of questions to explore
            show_output: Whether to print output to console

        Returns:
            List of result dictionaries
        """
        results = []
        for question in questions:
            result = self.explore_question(question, show_output)
            results.append(result)

        return results

    def log_to_database(self, user_prompt, generated_query, answer, question_gen_seconds, query_gen_seconds,
                        answer_gen_seconds, num_results, user_feedback, results_returned_fl):
        check_query = read_sql("SELECT distinct(sql_query) FROM aurora_discovered_kpis", self.mysql_engine)

        if generated_query in check_query.sql_query.tolist():
            self.console.print("Duplicate query found, skipping...")
            return

        with self.mysql_engine.connect() as conn:
            query = text("INSERT INTO aurora_discovered_kpis (question,sql_query,answer,question_gen_time_seconds,"
                         "query_gen_time_seconds,answer_gen_time_seconds) VALUES (:question,:sql_query,:answer,"
                         ":question_gen_time_seconds,:query_gen_time_seconds,:answer_gen_time_seconds)")
            conn.execute(query, {
                "question": user_prompt,
                "sql_query": generated_query,
                "answer": answer,
                "question_gen_time_seconds": question_gen_seconds,
                "query_gen_time_seconds": query_gen_seconds,
                "answer_gen_time_seconds": answer_gen_seconds
            })
            conn.commit()
            self.console.print("Query saved to database.")
