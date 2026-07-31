import textwrap


def with_solution_comments(code, explanation, language):
    """Prefix displayed solution code with readable approach comments."""
    code = str(code or "").strip()
    explanation = " ".join(str(explanation or "").split())
    if not explanation:
        explanation = "Follow the operations in order and verify the result after each step."

    prefix = "--" if language == "sql" else "#"
    comments = [f"{prefix} How this solution works:"]
    comments.extend(
        f"{prefix} {line}"
        for line in textwrap.wrap(explanation, width=88)
    )
    return "\n".join(comments + ["", code])
