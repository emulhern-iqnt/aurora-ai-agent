from sqlalchemy import create_engine
import pandas as pd
import os
import time


DB_USER: str = os.environ.get("DB_USER", "test")
DB_PASS: str = os.environ.get("DB_PASS", "test")
DB_HOST: str = os.environ.get("DB_HOST", "ssotest.oraclerac.inteliquent.com")
DB_SERVICE: str = os.environ.get("DB_SERVICE", "SSOTEST")


oracle_engine = create_engine(f"oracle+oracledb://{DB_USER}:{DB_PASS}@{DB_HOST}?service_name={DB_SERVICE}")
mysql_engine = create_engine(f"mysql+pymysql://root:zero@10.44.12.18/aurora_data")



print("Syncing step data...")

query = """
SELECT step.STEP_INSTANCE_ID,
       step.STEP_ID,
       step.ORDER_ID,
       service_order.PRODUCT_ID,
       service_order.SERVICE_MGR_NAME,
       step.ORDER_ITEM_ID,
       step.PROCESS_INSTANCE_ID,
       step.PROCESS_NAME,
       step.NAME,
       step.TYPE_WORKFLOW_ACTION_REF,
       step.ESTIMATED_DURATION,
       step.WORKGROUP_NAME as TEAM_NAME,
       step.WORKGROUP_PARTY_ROLE_ID AS TEAM_ID,
       step.EMPLOYEE_NAME,
       step.DUE_DT,
       CASE
           WHEN step.IS_AUTOMATED_STEP = 'Y' then 1
           ELSE 0
           END AS IS_AUTOMATED_STEP,
       CASE
           WHEN step.TYPE_WORKFLOW_ACTION_REF = 'COMPLETE' THEN ((step.UPDATE_DT - action.ACTION_DT) * 24)
           WHEN step.TYPE_WORKFLOW_ACTION_REF IN ('UNDO', 'UNDONE', 'REJECTED', 'PENDING', 'CNCL') THEN 0
           ELSE ((SYSDATE - action.ACTION_DT) * 24)
           END AS ELAPSED_DURATION_HOURS,
       step.UPDATE_DT,
       action.ACTION_DT
FROM VANILLA.V_STEP_INSTANCE step
         JOIN VANILLA.V_STEP_INSTANCE_ACTION action
              ON step.STEP_INSTANCE_ID = action.STEP_INSTANCE_ID
         RIGHT JOIN VANILLA.V_SERVICE_ORDER service_order
              ON step.ORDER_ID = service_order.ORDER_ID
WHERE action.TYPE_WORKFLOW_ACTION_REF = 'INSSTEP'
"""


start_ts = time.time()

df = pd.read_sql(query, oracle_engine)
df.to_sql("workflow_steps", mysql_engine, if_exists="replace")

print(f"Done. {time.time() - start_ts:.2f}s")
