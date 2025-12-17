# Airflow Integration

Run DQF from Airflow using Kubernetes, Docker or Bash operators.

KubernetesPodOperator example

```py
from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.kubernetes_pod import KubernetesPodOperator
from datetime import datetime

with DAG("dqf_validation", start_date=datetime(2025,1,1), schedule_interval="@daily", catchup=False) as dag:
    run_dqf = KubernetesPodOperator(
        task_id="run_dqf",
        name="dqf-validation",
        namespace="default",
        image="dqf:latest",
        cmds=["dqf"],
        arguments=[
            "--config-file", "sw_oracle_vs_bq",
            "--filetype", "yaml",
            "--vars", "env=prod",
            "run_label={{ ds_nodash }}",
        ],
        env_vars={
            "PROD_ORA_SW_CONN_STR": "oracle+oracledb://...",
            "PROD_BQ_ALL_CONN_STR": "bigquery://",
            "GCHAT_DQ_WEBHOOK": "https://chat.googleapis.com/...",
            "GOOGLE_APPLICATION_CREDENTIALS": "/path/to/creds.json",
        },
        get_logs=True,
        is_delete_operator_pod=True,
    )
```

DockerOperator example

```py
from airflow import DAG
from airflow.providers.docker.operators.docker import DockerOperator
from datetime import datetime

with DAG("dqf_validation", start_date=datetime(2025,1,1), schedule_interval="@daily", catchup=False) as dag:
    run_dqf = DockerOperator(
        task_id="run_dqf",
        image="dqf:latest",
        command="--config-file sw_oracle_vs_bq --filetype yaml --vars env=prod run_label={{ ds_nodash }}",
        environment={
            "PROD_ORA_SW_CONN_STR": "oracle+oracledb://...",
            "PROD_BQ_ALL_CONN_STR": "bigquery://",
            "GCHAT_DQ_WEBHOOK": "https://chat.googleapis.com/...",
            "GOOGLE_APPLICATION_CREDENTIALS": "/path/to/creds.json",
        },
        api_version="auto",
        auto_remove=True,
        mount_tmp_dir=False,
    )
```

BashOperator example

```py
from airflow.operators.bash import BashOperator

run_dqf = BashOperator(
    task_id="run_dqf",
    bash_command=(
        "source /path/to/venv/bin/activate && "
        "DQF_CONCURRENCY=8 dqf --config-file mxp_prod_replica_test --filetype yaml --vars env=prod run_label={{ ds_nodash }}"
    ),
    env={
        "PROD_MSSQL_REPLICA_CONN_STR": "mssql://...",
        "PROD_BQ_ALL_CONN_STR": "bigquery://",
    },
)
```

