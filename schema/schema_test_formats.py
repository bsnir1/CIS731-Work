import json
from jsonschema import validate, Draft202012Validator, FormatChecker
import jsonschema

with open("schema/vocadito_chunk.schema.json") as f: schema = json.load(f)
with open("schema/schema_vocadito_chunk_valid.json") as f: valid_doc = json.load(f)
with open("schema/schema_vocadito_chunk_invalid.json") as f: invalid_doc = json.load(f)

print("--- Validating Valid Record ---")
try:
    validate(instance=valid_doc, schema=schema, format_checker=FormatChecker())
    print("SUCCESS: Valid document passed.")
except jsonschema.exceptions.ValidationError as e:
    print(f"FAILED: {e.message}")

print("\n--- Validating Invalid Record (Date-Time) ---")
try:
    validate(instance=invalid_doc, schema=schema, format_checker=FormatChecker())
    print("FAILED: Invalid document was incorrectly accepted.")
except jsonschema.exceptions.ValidationError as e:
    print(f"SUCCESS: Invalid document correctly rejected.")
    print(f"Error caught: {e.message}")
