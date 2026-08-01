from core.terraform_simulator import execute_terraform_command, new_terraform_state


CONFIG = """
resource "aws_s3_bucket" "raw" {
  bucket = "raw"
}
resource "aws_glue_catalog_database" "lake" {
  name = "lake"
}
"""


def test_terraform_lifecycle_tracks_plan_apply_and_destroy():
    state, output = execute_terraform_command(new_terraform_state(), "terraform init", CONFIG)
    assert state["initialized"]
    assert "successfully initialized" in output

    state, output = execute_terraform_command(state, "terraform plan", CONFIG)
    assert "2 to add" in output

    state, output = execute_terraform_command(state, "terraform apply -auto-approve", CONFIG)
    assert len(state["resources"]) == 2
    assert "Apply complete" in output

    state, output = execute_terraform_command(state, "terraform state list", CONFIG)
    assert "aws_s3_bucket.raw" in output

    state, output = execute_terraform_command(state, "terraform destroy -auto-approve", CONFIG)
    assert not state["resources"]
    assert "2 destroyed" in output


def test_terraform_workspaces_and_import_are_isolated():
    state, _ = execute_terraform_command(new_terraform_state(), "terraform workspace new dev", CONFIG)
    assert state["workspace"] == "dev"
    state, output = execute_terraform_command(
        state,
        "terraform import aws_s3_bucket.existing bucket-123",
        CONFIG,
    )
    assert "Import successful" in output
    assert state["resources"]["aws_s3_bucket.existing"]["id"] == "bucket-123"
