from core.aws_simulator import (
    AWS_CLI_LABS,
    execute_aws_cli,
    new_aws_cli_state,
    service_mastery,
)


def test_every_aws_service_has_executable_guided_commands():
    state = new_aws_cli_state()
    for service, commands in AWS_CLI_LABS.items():
        assert len(commands) >= 3
        for command in commands:
            state, output = execute_aws_cli(state, command)
            assert not output.startswith("error:"), (service, command, output)
        mastery = service_mastery(service, state)
        assert mastery["percent"] == 100, (service, mastery)


def test_aws_cli_persists_resources_and_reports_access_denied():
    state, output = execute_aws_cli(
        new_aws_cli_state(),
        "aws kinesis create-stream --stream-name orders",
    )
    assert '"status": "ACTIVE"' in output
    assert state["resources"]["Kinesis Data Streams"][0]["name"] == "orders"

    denied_state, denied = execute_aws_cli(
        state,
        "aws kinesis put-record --stream-name orders --data event --simulate-access-denied",
    )
    assert "AccessDeniedException" in denied
    assert denied_state["executions"] == state["executions"]


def test_aws_cli_rejects_host_shell_operators():
    _, output = execute_aws_cli(
        new_aws_cli_state(),
        "aws s3api list-buckets; whoami",
    )
    assert "shell operators are disabled" in output
