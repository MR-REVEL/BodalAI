import json
import sys
from pathlib import Path

try:
    # jsonschema>=4.18 supports 2020-12 via Draft202012Validator
    from jsonschema import Draft202012Validator, validate
    from jsonschema.exceptions import ValidationError, SchemaError
except Exception as e:
    print("jsonschema package is required. Install with: pip install jsonschema>=4.18.0")
    raise


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main():
    repo_root = Path(__file__).resolve().parents[1]
    schema_path = repo_root / "schemas" / "trp.schema.json"
    example_path = repo_root / "schemas" / "examples" / "valid_trp.json"

    # Load schema
    try:
        schema = load_json(schema_path)
    except Exception as e:
        print(f"FAIL: Could not load schema at {schema_path}: {e}")
        sys.exit(1)

    # Compile schema (check it is valid against meta-schema)
    try:
        Draft202012Validator.check_schema(schema)
        print("PASS: Schema compiles against draft 2020-12 meta-schema.")
    except SchemaError as e:
        print("FAIL: Schema is invalid against draft 2020-12 meta-schema.\n")
        print(e)
        sys.exit(2)

    # Validate example instance
    try:
        instance = load_json(example_path)
    except Exception as e:
        print(f"FAIL: Could not load example instance at {example_path}: {e}")
        sys.exit(3)

    try:
        Draft202012Validator(schema).validate(instance)
        print("PASS: Example instance validates against schema.")
    except ValidationError as e:
        print("FAIL: Example instance does not validate against schema.\n")
        print(e)
        sys.exit(4)


if __name__ == "__main__":
    main()
