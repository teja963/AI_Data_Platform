import copy
import json
import shlex
from datetime import datetime, timezone


AWS_CLI_LABS = {
    "S3": [
        "aws s3api create-bucket --bucket de-raw-zone --region us-east-1",
        "aws s3api put-bucket-versioning --bucket de-raw-zone --status Enabled",
        "aws s3api list-buckets",
    ],
    "Glue Data Catalog": [
        "aws glue create-database --name analytics",
        "aws glue create-table --database-name analytics --name orders",
        "aws glue get-tables --database-name analytics",
    ],
    "Glue Crawler": [
        "aws glue create-crawler --name orders-crawler --database-name analytics --target s3://de-raw-zone/orders/",
        "aws glue start-crawler --name orders-crawler",
        "aws glue get-crawler --name orders-crawler",
    ],
    "Glue ETL Job": [
        "aws glue create-job --name orders-etl --role GlueExecutionRole --script-location s3://de-scripts/orders.py",
        "aws glue start-job-run --job-name orders-etl",
        "aws glue get-job-runs --job-name orders-etl",
    ],
    "Lake Formation": [
        "aws lakeformation register-resource --resource-arn arn:aws:s3:::de-curated",
        "aws lakeformation grant-permissions --principal AnalystRole --resource analytics.orders --permissions SELECT",
        "aws lakeformation list-permissions",
    ],
    "Lambda": [
        "aws lambda create-function --function-name validate-orders --runtime python3.12 --role PipelineRole",
        "aws lambda invoke --function-name validate-orders --payload '{\"bucket\":\"de-raw-zone\"}'",
        "aws lambda get-function --function-name validate-orders",
    ],
    "Step Functions": [
        "aws stepfunctions create-state-machine --name orders-pipeline --role-arn PipelineRole",
        "aws stepfunctions start-execution --state-machine-arn orders-pipeline",
        "aws stepfunctions list-executions --state-machine-arn orders-pipeline",
    ],
    "EventBridge": [
        "aws events put-rule --name ingestion-complete --event-pattern BatchCompleted",
        "aws events put-targets --rule ingestion-complete --targets orders-pipeline",
        "aws events list-rules",
    ],
    "Athena": [
        "aws athena start-query-execution --query-string 'SELECT count(*) FROM analytics.orders' --work-group analytics",
        "aws athena get-query-results --query-execution-id latest",
        "aws athena list-query-executions --work-group analytics",
    ],
    "Redshift": [
        "aws redshift-serverless create-workgroup --workgroup-name analytics --base-capacity 32",
        "aws redshift-data execute-statement --workgroup-name analytics --database dev --sql 'COPY orders FROM s3://de-curated/orders/'",
        "aws redshift-serverless get-workgroup --workgroup-name analytics",
    ],
    "EMR": [
        "aws emr-serverless create-application --name spark-etl --type SPARK",
        "aws emr-serverless start-job-run --application-id spark-etl --execution-role-arn EmrRole",
        "aws emr-serverless list-job-runs --application-id spark-etl",
    ],
    "Kinesis Data Streams": [
        "aws kinesis create-stream --stream-name orders --stream-mode-details ON_DEMAND",
        "aws kinesis put-record --stream-name orders --partition-key customer-101 --data order-1",
        "aws kinesis describe-stream-summary --stream-name orders",
    ],
    "Firehose": [
        "aws firehose create-delivery-stream --delivery-stream-name orders-to-s3 --destination S3",
        "aws firehose put-record --delivery-stream-name orders-to-s3 --record order-1",
        "aws firehose describe-delivery-stream --delivery-stream-name orders-to-s3",
    ],
    "MSK": [
        "aws kafka create-cluster-v2 --cluster-name orders-msk --provisioned 3-brokers",
        "aws kafka update-monitoring --cluster-arn orders-msk --enhanced-monitoring PER_TOPIC_PER_PARTITION",
        "aws kafka list-clusters-v2",
    ],
    "RDS / Aurora": [
        "aws rds create-db-cluster --db-cluster-identifier orders-aurora --engine aurora-postgresql",
        "aws rds create-db-instance --db-instance-identifier orders-writer --db-cluster-identifier orders-aurora",
        "aws rds describe-db-clusters",
    ],
    "DynamoDB": [
        "aws dynamodb create-table --table-name PipelineRuns --partition-key pipeline_id --sort-key execution_ts",
        "aws dynamodb put-item --table-name PipelineRuns --item pipeline-1:running",
        "aws dynamodb scan --table-name PipelineRuns",
    ],
    "Neptune": [
        "aws neptune create-db-cluster --db-cluster-identifier lineage-graph --engine neptune",
        "aws neptune create-db-instance --db-instance-identifier lineage-reader --db-cluster-identifier lineage-graph",
        "aws neptune describe-db-clusters",
    ],
    "DMS": [
        "aws dms create-replication-task --replication-task-identifier postgres-to-s3 --migration-type full-load-and-cdc",
        "aws dms start-replication-task --replication-task-arn postgres-to-s3",
        "aws dms describe-replication-tasks",
    ],
    "IAM": [
        "aws iam create-role --role-name GlueExecutionRole --trust-policy glue.amazonaws.com",
        "aws iam put-role-policy --role-name GlueExecutionRole --policy-name AnalyticsS3Access",
        "aws iam get-role --role-name GlueExecutionRole",
    ],
    "KMS": [
        "aws kms create-key --description data-platform-key",
        "aws kms create-alias --alias-name alias/data-platform --target-key-id latest",
        "aws kms list-aliases",
    ],
    "Secrets Manager": [
        "aws secretsmanager create-secret --name analytics/redshift --secret-string simulated-password",
        "aws secretsmanager rotate-secret --secret-id analytics/redshift --rotation-days 30",
        "aws secretsmanager describe-secret --secret-id analytics/redshift",
    ],
    "CloudWatch": [
        "aws cloudwatch put-metric-alarm --alarm-name PipelineFailures --metric-name FailedExecutions --threshold 1",
        "aws cloudwatch put-metric-data --namespace DataPlatform --metric-name PipelineLatency --value 42",
        "aws cloudwatch describe-alarms",
    ],
    "Bedrock Knowledge Bases": [
        "aws bedrock-agent create-knowledge-base --name engineering-runbooks --vector-store OpenSearchServerless",
        "aws bedrock-agent start-ingestion-job --knowledge-base-id engineering-runbooks --data-source-id s3-runbooks",
        "aws bedrock-agent list-knowledge-bases",
    ],
    "OpenSearch": [
        "aws opensearchserverless create-collection --name pipeline-search --type SEARCH",
        "aws opensearchserverless create-collection --name runbook-vectors --type VECTORSEARCH",
        "aws opensearchserverless list-collections",
    ],
}


CLI_SERVICE_MAP = {
    "s3": "S3",
    "s3api": "S3",
    "glue": None,
    "lakeformation": "Lake Formation",
    "lambda": "Lambda",
    "stepfunctions": "Step Functions",
    "events": "EventBridge",
    "athena": "Athena",
    "redshift-serverless": "Redshift",
    "redshift-data": "Redshift",
    "emr-serverless": "EMR",
    "kinesis": "Kinesis Data Streams",
    "firehose": "Firehose",
    "kafka": "MSK",
    "rds": "RDS / Aurora",
    "dynamodb": "DynamoDB",
    "neptune": "Neptune",
    "dms": "DMS",
    "iam": "IAM",
    "kms": "KMS",
    "secretsmanager": "Secrets Manager",
    "cloudwatch": "CloudWatch",
    "bedrock-agent": "Bedrock Knowledge Bases",
    "opensearchserverless": "OpenSearch",
}


def new_aws_cli_state():
    return {
        "region": "us-east-1",
        "account_id": "123456789012",
        "resources": {service: [] for service in AWS_CLI_LABS},
        "executions": [],
        "counter": 0,
    }


def normalize_aws_cli_state(state):
    working = copy.deepcopy(state) if isinstance(state, dict) else new_aws_cli_state()
    working.setdefault("region", "us-east-1")
    working.setdefault("account_id", "123456789012")
    working.setdefault("resources", {})
    for service in AWS_CLI_LABS:
        working["resources"].setdefault(service, [])
    working.setdefault("executions", [])
    working.setdefault("counter", 0)
    return working


def _flag(tokens, *names, default=None):
    for name in names:
        if name in tokens:
            index = tokens.index(name)
            if index + 1 < len(tokens):
                return tokens[index + 1]
    return default


def _resource_name(service, action, tokens, counter):
    flag_names = (
        "--bucket",
        "--name",
        "--database-name",
        "--table-name",
        "--function-name",
        "--stream-name",
        "--delivery-stream-name",
        "--cluster-name",
        "--db-cluster-identifier",
        "--db-instance-identifier",
        "--replication-task-identifier",
        "--role-name",
        "--alias-name",
        "--secret-id",
        "--alarm-name",
        "--workgroup-name",
        "--application-id",
        "--knowledge-base-id",
    )
    return _flag(tokens, *flag_names, default=f"{service.lower().replace(' ', '-')}-{counter}")


def _resolve_service(cli_service, action):
    if cli_service == "glue":
        if "crawler" in action:
            return "Glue Crawler"
        if "job" in action:
            return "Glue ETL Job"
        return "Glue Data Catalog"
    return CLI_SERVICE_MAP.get(cli_service)


def _is_read_action(action):
    return action.startswith(
        ("get", "list", "describe", "scan", "batch-get", "lookup")
    )


def _is_delete_action(action):
    return action.startswith(("delete", "remove", "deregister"))


def execute_aws_cli(state, command):
    command = (command or "").strip()
    if not command:
        return normalize_aws_cli_state(state), ""
    try:
        tokens = shlex.split(command)
    except ValueError as error:
        return normalize_aws_cli_state(state), f"error: {error}"
    if len(tokens) < 3 or tokens[0] != "aws":
        return normalize_aws_cli_state(state), "error: command must start with aws SERVICE ACTION"
    if any(operator in command for operator in (";", "&&", "||", "`", "$(")):
        return normalize_aws_cli_state(state), "error: shell operators are disabled in the simulator"

    working = normalize_aws_cli_state(state)
    cli_service, action = tokens[1].lower(), tokens[2].lower()
    service = _resolve_service(cli_service, action)
    if not service:
        return working, f"error: AWS service '{cli_service}' is not supported"
    if "--simulate-access-denied" in tokens:
        return working, (
            "An error occurred (AccessDeniedException): the simulated principal is not "
            f"authorized to perform {cli_service}:{action}"
        )

    working["counter"] += 1
    resource_name = _resource_name(service, action, tokens, working["counter"])
    resources = working["resources"][service]
    now = datetime.now(timezone.utc).isoformat()

    if _is_read_action(action):
        payload = {
            "service": service,
            "region": working["region"],
            "resources": resources,
            "count": len(resources),
        }
    elif _is_delete_action(action):
        before = len(resources)
        working["resources"][service] = [
            resource for resource in resources if resource["name"] != resource_name
        ]
        payload = {
            "service": service,
            "resource": resource_name,
            "deleted": len(working["resources"][service]) < before,
        }
    else:
        existing = next(
            (resource for resource in resources if resource["name"] == resource_name),
            None,
        )
        resource = existing or {
            "name": resource_name,
            "arn": (
                f"arn:aws:{cli_service}:{working['region']}:"
                f"{working['account_id']}:{resource_name}"
            ),
            "created_at": now,
        }
        resource.update(
            {
                "last_action": action,
                "status": (
                    "RUNNING"
                    if action.startswith(("start", "invoke", "execute", "put"))
                    else "ACTIVE"
                ),
            }
        )
        if not existing:
            resources.append(resource)
        payload = {
            "service": service,
            "action": action,
            "resource": resource,
            "request_id": f"sim-{working['counter']:06d}",
        }

    working["executions"].append(
        {
            "time": now,
            "service": service,
            "action": action,
            "command": command,
            "status": "SUCCEEDED",
        }
    )
    working["executions"] = working["executions"][-200:]
    return working, json.dumps(payload, indent=2)


def service_mastery(service, state):
    working = normalize_aws_cli_state(state)
    expected_actions = {
        shlex.split(command)[2]
        for command in AWS_CLI_LABS[service]
        if len(shlex.split(command)) >= 3
    }
    completed_actions = {
        execution["action"]
        for execution in working["executions"]
        if execution["service"] == service and execution["status"] == "SUCCEEDED"
    }
    completed = len(expected_actions & completed_actions)
    total = len(expected_actions)
    return {
        "completed": completed,
        "total": total,
        "percent": round(completed / total * 100) if total else 0,
        "remaining": sorted(expected_actions - completed_actions),
    }
