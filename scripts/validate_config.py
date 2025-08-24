
#!/usr/bin/env python3
import argparse, json, sys, yaml, pathlib
from jsonschema import validate, ValidationError

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    cfg_path = pathlib.Path(args.config)
    schema_path = (pathlib.Path(__file__).parent / ".." / "schemas" / "config.schema.json").resolve()
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    try:
        validate(cfg, schema)
        print("[OK] Config valid:", cfg_path)
    except ValidationError as e:
        print("[ERROR] Config invalid:", e.message)
        sys.exit(2)

if __name__ == "__main__":
    main()


