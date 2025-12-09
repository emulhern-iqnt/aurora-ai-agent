# aurora-ai-agent
Tim's kpi_explorer file:

selects all entries from the aurora_discovered_kpis table.
Joins them together as 'old_questions' (or if they don't exist, set to 'No previous questions')

Loads old_questions_str into the question_prompt_template format (along with workflows_schema and sample_data) and invokes the explorer_llm_so with it
Pulls the question off the respose from the explorer_llm_so

Feeds the question and the relevant schema into the code_prompt_template format and invokes the sql_llm_so
Takes the response from the sql_llm_so and pulls the sql_query out of it

Executes the sql_query 
Feeds the results, the query, and the question to the answer_prompt_template format and invokes the answer_llm_so with it
    

