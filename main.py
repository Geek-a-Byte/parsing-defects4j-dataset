"""
Defects4J Synthetic Log Generator

This pipeline extracts real test outputs from Defects4J and generates
comprehensive debugging logs for each bug, combining:
1. Real stack traces and test failures (logs)
2. Bug descriptions and triggering tests (bug)
3. Actual fixes from commits (patch)

WHAT IS DEFECTS4J?
Defects4J is a database of real bugs from Java projects. Each bug has:
- A buggy version (the broken code)
- A fixed version (the corrected code)
- Tests that fail on buggy version but pass on fixed version
- Information about what was changed to fix the bug
"""

import json
import subprocess
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
import xml.etree.ElementTree as ET

#from dataset_exporter import DatasetExporter
from defects_manager import Defects4JManager
#from synthetic_log_generator import SyntheticLogGenerator


def main():
    """
    Main pipeline execution.
    This orchestrates the entire process of:
    1. Getting bugs from Defects4J
    2. Running tests to get real failures
    3. Generating synthetic logs
    4. Exporting the results
    """

    # === CONFIGURATION ===
    # Directory to store temporary files
    work_dir = Path("./defects4j_work")
    work_dir.mkdir(exist_ok=True)  # Create if doesn't exist

    # Directory for output files
    # output_dir = Path("./synthetic_logs")
    # output_dir.mkdir(exist_ok=True)

    # === INITIALIZE COMPONENTS ===
    d4j = Defects4JManager()  # Handles Defects4J operations
    # generator = SyntheticLogGenerator()  # Creates synthetic logs
    # exporter = DatasetExporter()  # Exports data to files

    # === DISPLAY AVAILABLE PROJECTS ===
    print("=" * 80)
    print("Available Defects4J Projects:")
    print("=" * 80)
    for i, project in enumerate(d4j.projects, 1):
        # Get number of bugs in each project
        bug_count = len(d4j.get_all_bugs(project))
        print(f"{i:2}. {project:20} ({bug_count} bugs)")
    print("=" * 80)

    # === PROCESS BUGS ===
    sessions = []  # Store all generated debug sessions

    # Example: Process first 5 bugs from Lang project
    # You can change this to process different projects or more bugs
    project = "Mockito"
    print(f"\nProcessing {project} project...")

    # Get list of all bug IDs for this project
    bug_ids = d4j.get_all_bugs(project)  # Take first 5 bugs only

    # Process each bug
    for bug_id in bug_ids:
        print(f"\nProcessing {project} bug {bug_id}...")

        try:
            # Step 1: Get bug information from Defects4J
            bug_info = d4j.get_bug_info(project, bug_id)

            # Step 2: Download the buggy version of the code
            checkout_path = d4j.checkout_bug(project, bug_id, work_dir)
            bug_info.checkout_path = checkout_path

            # Step 3: Run the failing tests to get real error messages
            test_outputs = d4j.run_tests(checkout_path, bug_info.triggering_tests)
            print(f"  Retrieved {len(test_outputs)} test outputs")

            # Step 4: Get the patch that fixed the bug
            bug_info.patch = d4j.export_patch(project, bug_id, work_dir)
            
            with open("failing_tests.log", "a", encoding="utf-8") as nf:
                nf.write(f"report for {project}-{bug_id}:\n{bug_info.bug_report_url}\n")
                nf.write(f"patch for {project}-{bug_id}:\n{bug_info.patch}\n")
                nf.write("\n\n")  # two blank lines between entries

            # Step 5: Generate synthetic debug session
            # session = generator.generate_debug_session(bug_info, test_outputs)
            # sessions.append(session)

            # Print summary
            # print(f"  Generated {len(session.log_sequence)} log entries")
            # print(f"  Root cause: {session.root_cause_summary}")

        except Exception as e:
            # If something goes wrong, log it and continue with next bug
            print(f"  Error processing {project}-{bug_id}: {e}")
            import traceback
            traceback.print_exc()
            continue

    # === EXPORT RESULTS ===
    # print(f"\nExporting {len(sessions)} debug sessions...")
    # exporter.export_to_json(sessions, output_dir / "debug_sessions.json")
    # exporter.export_to_jsonl(sessions, output_dir / "debug_sessions.jsonl")

    # print(f"Done! Output saved to {output_dir}")

    # === SHOW SAMPLE OUTPUT ===
    # if sessions:
    #     print("\n" + "=" * 80)
    #     print("Sample Debug Session:")
    #     print("=" * 80)
    #     sample = sessions[0]  # Show first session as example
    #     print(f"Bug: {sample.bug_info.project}-{sample.bug_info.bug_id}")
        
    #     print(f"\nTimeline:")
    #     for step in sample.investigation_timeline:
    #         print(f"  - {step}")
            
    #     print(f"\nLog Sample (first 5 entries):")
    #     for log in sample.log_sequence[:5]:
    #         print(
    #             f"  [{log.timestamp}] {log.level:8} | {log.source:12} | {log.message}"
    #         )


# This is the entry point when running the script
if __name__ == "__main__":
    main()
