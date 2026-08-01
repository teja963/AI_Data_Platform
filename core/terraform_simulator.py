import copy
import re
import shlex


RESOURCE_PATTERN = re.compile(
    r'resource\s+"(?P<type>[a-zA-Z0-9_]+)"\s+"(?P<name>[a-zA-Z0-9_-]+)"\s*\{',
    re.MULTILINE,
)


def new_terraform_state():
    return {
        "initialized": False,
        "workspace": "default",
        "workspaces": ["default"],
        "resources": {},
        "outputs": {},
        "last_plan": [],
        "config": "",
        "transcript": [],
    }


def normalize_terraform_state(state):
    normalized = new_terraform_state()
    if isinstance(state, dict):
        for key in normalized:
            if key in state:
                normalized[key] = copy.deepcopy(state[key])
    normalized["workspaces"] = sorted(set(normalized["workspaces"] or ["default"]))
    if normalized["workspace"] not in normalized["workspaces"]:
        normalized["workspaces"].append(normalized["workspace"])
    return normalized


def parse_terraform_resources(config):
    return [
        {
            "address": f"{match.group('type')}.{match.group('name')}",
            "type": match.group("type"),
            "name": match.group("name"),
        }
        for match in RESOURCE_PATTERN.finditer(config or "")
    ]


def _plan(state, config):
    desired = {item["address"]: item for item in parse_terraform_resources(config)}
    current = state["resources"]
    rows = []
    for address, resource in desired.items():
        rows.append(
            {
                "action": "no-op" if address in current else "create",
                "address": address,
                "type": resource["type"],
            }
        )
    for address, resource in current.items():
        if address not in desired:
            rows.append({"action": "destroy", "address": address, "type": resource["type"]})
    return rows


def _resource_id(resource, workspace):
    safe_type = resource["type"].replace("_", "-")
    return f"sim-{workspace}-{safe_type}-{resource['name']}"


def execute_terraform_command(state, command, config):
    working = normalize_terraform_state(state)
    cleaned = (command or "").strip()
    if not cleaned:
        return working, ""
    if any(operator in cleaned for operator in ("&&", "||", ";", "|", ">", "<")):
        return working, "Error: shell operators are not supported in the virtual Terraform terminal."
    try:
        args = shlex.split(cleaned)
    except ValueError as error:
        return working, f"Error: {error}"
    if args and args[0] == "terraform":
        args = args[1:]
    if not args:
        return working, "Terraform virtual CLI. Try: terraform init, validate, plan, apply, state list, destroy."

    verb = args[0]
    output = ""
    if verb == "init":
        working["initialized"] = True
        output = (
            "Initializing the backend...\n"
            f"Workspace: {working['workspace']}\n"
            "Initializing provider plugins...\n"
            "Terraform has been successfully initialized!"
        )
    elif verb == "fmt":
        output = "main.tf"
    elif verb == "validate":
        if not working["initialized"]:
            output = "Error: run terraform init before validation."
        elif (config or "").count("{") != (config or "").count("}"):
            output = "Error: unbalanced braces in main.tf."
        elif not parse_terraform_resources(config):
            output = "Warning: configuration is valid but declares no resources."
        else:
            output = "Success! The configuration is valid."
    elif verb == "plan":
        if not working["initialized"]:
            output = "Error: run terraform init before planning."
        else:
            rows = _plan(working, config)
            working["last_plan"] = rows
            create_count = sum(row["action"] == "create" for row in rows)
            destroy_count = sum(row["action"] == "destroy" for row in rows)
            changes = [
                f"  {'+' if row['action'] == 'create' else '-' if row['action'] == 'destroy' else '='} "
                f"{row['address']} ({row['action']})"
                for row in rows
            ]
            output = "\n".join(changes) + f"\n\nPlan: {create_count} to add, 0 to change, {destroy_count} to destroy."
    elif verb == "apply":
        if not working["initialized"]:
            output = "Error: run terraform init before apply."
        else:
            plan = _plan(working, config)
            desired = parse_terraform_resources(config)
            working["resources"] = {
                item["address"]: {
                    **item,
                    "id": _resource_id(item, working["workspace"]),
                    "workspace": working["workspace"],
                    "status": "created",
                }
                for item in desired
            }
            working["config"] = config
            working["last_plan"] = plan
            working["outputs"] = {
                "workspace": working["workspace"],
                "resource_count": len(desired),
            }
            output = (
                "\n".join(f"{item['address']}: Creation complete" for item in desired)
                + f"\n\nApply complete! Resources: {len(desired)} added or retained."
            )
    elif verb == "destroy":
        count = len(working["resources"])
        working["resources"] = {}
        working["outputs"] = {}
        working["last_plan"] = []
        output = f"Destroy complete! Resources: {count} destroyed."
    elif verb == "show":
        output = "\n".join(
            f'{address}:\n  id = "{resource["id"]}"\n  workspace = "{resource["workspace"]}"'
            for address, resource in working["resources"].items()
        ) or "The state file is empty."
    elif verb == "output":
        output = "\n".join(f"{key} = {value}" for key, value in working["outputs"].items()) or "No outputs found."
    elif verb == "providers":
        providers = sorted(
            {
                resource["type"].split("_", 1)[0]
                for resource in parse_terraform_resources(config)
            }
        )
        output = "Providers required by configuration:\n" + "\n".join(f"- {item}" for item in providers)
    elif verb == "state":
        action = args[1] if len(args) > 1 else "list"
        if action == "list":
            output = "\n".join(sorted(working["resources"])) or "No resources in state."
        elif action == "show" and len(args) > 2:
            address = args[2]
            resource = working["resources"].get(address)
            output = (
                "\n".join(f"{key} = {value}" for key, value in resource.items())
                if resource
                else f"Error: resource address {address!r} not found."
            )
        elif action == "rm" and len(args) > 2:
            address = args[2]
            removed = working["resources"].pop(address, None)
            output = f"Removed {address} from state." if removed else f"Error: {address} not found."
        else:
            output = "Usage: terraform state list | show ADDRESS | rm ADDRESS"
    elif verb == "workspace":
        action = args[1] if len(args) > 1 else "list"
        if action == "list":
            output = "\n".join(
                f"{'*' if item == working['workspace'] else ' '} {item}"
                for item in working["workspaces"]
            )
        elif action == "new" and len(args) > 2:
            name = args[2]
            if name not in working["workspaces"]:
                working["workspaces"].append(name)
            working["workspace"] = name
            working["resources"] = {}
            output = f'Created and switched to workspace "{name}".'
        elif action == "select" and len(args) > 2:
            name = args[2]
            if name not in working["workspaces"]:
                output = f'Error: workspace "{name}" does not exist.'
            else:
                working["workspace"] = name
                working["resources"] = {}
                output = f'Switched to workspace "{name}".'
        else:
            output = "Usage: terraform workspace list | new NAME | select NAME"
    elif verb == "import" and len(args) > 2:
        address, resource_id = args[1], args[2]
        resource_type, _, name = address.partition(".")
        if not name:
            output = "Error: import address must use TYPE.NAME."
        else:
            working["resources"][address] = {
                "address": address,
                "type": resource_type,
                "name": name,
                "id": resource_id,
                "workspace": working["workspace"],
                "status": "imported",
            }
            output = f"{address}: Import successful!"
    else:
        output = f"Error: unsupported Terraform command {verb!r}."

    working["transcript"].append({"command": cleaned, "output": output})
    working["transcript"] = working["transcript"][-100:]
    return working, output
