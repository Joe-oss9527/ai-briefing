
#!/usr/bin/env python3
import argparse
from briefing import run

def main():
    ap = argparse.ArgumentParser(description="AI-Briefing CLI")
    ap.add_argument("--config", required=True, help="Path to YAML config")
    args = ap.parse_args()
    run(args.config)

if __name__ == "__main__":
    main()
