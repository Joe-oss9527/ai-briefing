
# briefing/output_validator.py
import json
from jsonschema import validate, Draft202012Validator
from jsonschema.exceptions import ValidationError

def validate_briefing(obj: dict, schema_str: str):
    schema = json.loads(schema_str)
    try:
        validate(instance=obj, schema=schema, cls=Draft202012Validator)
    except ValidationError as e:
        path = list(e.path)
        raise ValueError(f"Briefing JSON invalid: {e.message} at {path}") from e


