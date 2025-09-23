
#!/usr/bin/env python3
import argparse

from briefing.orchestrator import run_once


def main():
    parser = argparse.ArgumentParser(description="AI-Briefing CLI")
    parser.add_argument("--config", required=True, help="Path to YAML config")
    parser.add_argument("--multi-stage", dest="multi_stage", action="store_true", help="Enable multi-stage LLM pipeline")
    parser.add_argument("--single-stage", dest="multi_stage", action="store_false", help="Force legacy single-stage summarization")
    parser.add_argument("--agentic-section", dest="agentic_section", action="store_true", help="Force Agentic Focus section output when possible")
    parser.add_argument("--no-agentic-section", dest="agentic_section", action="store_false", help="Disable Agentic Focus section even if configured")
    parser.add_argument("--brief-lite", dest="brief_lite", action="store_true", help="Emit additional condensed brief if supported")
    parser.add_argument("--no-brief-lite", dest="brief_lite", action="store_false", help="Skip condensed brief generation")
    parser.set_defaults(multi_stage=None, agentic_section=None, brief_lite=None)
    args = parser.parse_args()

    run_once(
        args.config,
        multi_stage=args.multi_stage,
        agentic_section=args.agentic_section,
        brief_lite=args.brief_lite,
    )


if __name__ == "__main__":
    main()
