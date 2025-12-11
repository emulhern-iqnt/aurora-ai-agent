# aurora-ai-agent
1. Grab a random KPI from the table and print it as a suggestion
2. Prompt the user to either exit, enter their own question, or explore
    a. If the user enters their own question:
        i. Utilize the sql_llm to generate a sql query based on the user's question
        ii. Execute the query and utilize the answer llm to translate the results into a response
        iii. If the query succeeds, save the qeustion and the generated query to the prompt_logs table
        iv.  If the query fails, save the error to a list
    b. If the user wants to explore for KPIs:
        i. Ask the user how many questions they want to generate
        ii. Generate questions via the explorer llm
        iii. Create SQL queries based on each question and execute them
        iV. If the query succeeds, attempt to save it to the database along with the question that spawned it (check for duplicate first)
        iv. If the query fails, save the error to a list
3. Combine any SQL errors made by the KPI Explorer or the Prompt into a single list
4. Run the above SQL errors through the SQL LLM
5. Append them to the main 'question prompt'

