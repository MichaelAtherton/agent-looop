"""Parser fixture used by smoke-test issues."""


def parse_input(value: str) -> list[str]:
    """Parse a comma-separated string into trimmed non-empty tokens.

    Empty input should raise ValueError. A future smoke-test issue asks the
    worker to add an explicit regression test for that behavior.
    """
    if value == "":
        raise ValueError("input cannot be empty")

    return [part.strip() for part in value.split(",") if part.strip()]
