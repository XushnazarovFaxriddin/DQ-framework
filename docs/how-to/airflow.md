# Airflow Integration

Run DQF from Airflow using Kubernetes, Docker or Bash operators.

## Alert Integration

DQF can include Airflow context in alerts (Google Chat, Email) when these environment variables are set:

| Variable | Description | Example |
|----------|-------------|---------|
| `AIRFLOW_DAG_ID` | DAG identifier | `{{ dag.dag_id }}` |
| `AIRFLOW_TASK_ID` | Task identifier | `{{ task.task_id }}` |
| `AIRFLOW_DAG_RUN_ID` | DAG run identifier | `{{ dag_run.run_id }}` |
| `AIRFLOW_EXECUTION_DATE` | Execution date | `{{ ds }}` |
| `AIRFLOW_BASE_URL` | Airflow UI base URL | `https://airflow.example.com` |
| `AIRFLOW_LOG_URL` | Direct task log URL (optional) | Computed if base URL set |
| `AIRFLOW_DAG_URL` | Direct DAG URL (optional) | Computed if base URL set |

When set, alerts include:
- DAG and task identification
- Clickable links to task logs and DAG view
- Execution date for reference

## KubernetesPodOperator example

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
            # Connection strings
            "PROD_ORA_SW_CONN_STR": "oracle+oracledb://...",
            "PROD_BQ_ALL_CONN_STR": "bigquery://",
            "GCHAT_DQ_WEBHOOK": "https://chat.googleapis.com/...",
            "GOOGLE_APPLICATION_CREDENTIALS": "/path/to/creds.json",
            # Airflow context for alerts
            "AIRFLOW_DAG_ID": "{{ dag.dag_id }}",
            "AIRFLOW_TASK_ID": "{{ task.task_id }}",
            "AIRFLOW_DAG_RUN_ID": "{{ dag_run.run_id }}",
            "AIRFLOW_EXECUTION_DATE": "{{ ds }}",
            "AIRFLOW_BASE_URL": "https://airflow.yourcompany.com",
        },
        get_logs=True,
        is_delete_operator_pod=True,
    )
```

## DockerOperator example

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
            # Airflow context for alerts
            "AIRFLOW_DAG_ID": "{{ dag.dag_id }}",
            "AIRFLOW_TASK_ID": "{{ task.task_id }}",
            "AIRFLOW_DAG_RUN_ID": "{{ dag_run.run_id }}",
            "AIRFLOW_EXECUTION_DATE": "{{ ds }}",
            "AIRFLOW_BASE_URL": "https://airflow.yourcompany.com",
        },
        api_version="auto",
        auto_remove=True,
        mount_tmp_dir=False,
    )
```

## BashOperator example

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
        # Airflow context for alerts
        "AIRFLOW_DAG_ID": "{{ dag.dag_id }}",
        "AIRFLOW_TASK_ID": "{{ task.task_id }}",
        "AIRFLOW_DAG_RUN_ID": "{{ dag_run.run_id }}",
        "AIRFLOW_EXECUTION_DATE": "{{ ds }}",
        "AIRFLOW_BASE_URL": "https://airflow.yourcompany.com",
    },
)
```

## Email Alerts from Airflow

To enable email alerts with SendGrid:

```py
env_vars={
    # ... other vars ...
    "DQF_EMAIL_BACKEND": "sendgrid",
    "SENDGRID_API_KEY": Variable.get("sendgrid_api_key"),
    "SENDGRID_FROM": "dqf@yourcompany.com",
    "DQ_EMAILS": "team@yourcompany.com,oncall@yourcompany.com",
}
```

Or with SMTP:

```py
env_vars={
    # ... other vars ...
    "SMTP_HOST": "smtp.yourcompany.com",
    "SMTP_PORT": "587",
    "SMTP_USER": Variable.get("smtp_user"),
    "SMTP_PASS": Variable.get("smtp_pass"),
    "SMTP_FROM": "dqf@yourcompany.com",
    "DQ_EMAILS": "team@yourcompany.com",
}
```

