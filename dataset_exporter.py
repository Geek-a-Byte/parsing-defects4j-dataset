import json
import subprocess
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
import xml.etree.ElementTree as ET

from utils import SyntheticDebugSession

class DatasetExporter:
    """
    Export generated debug sessions to various file formats.
    This allows the data to be used for training or analysis.
    """

    def export_to_json(self, sessions: List[SyntheticDebugSession], output_path: Path):
        """
        Export all sessions to a single JSON file.
        JSON is human-readable and good for small datasets.
        """
        data = []

        for session in sessions:
            # Convert each session to a dictionary
            entry = {
                "bug_id": f"{session.bug_info.project}_{session.bug_info.bug_id}",
                "project": session.bug_info.project,
                "bug_info": asdict(session.bug_info),  # Convert dataclass to dict
                "logs": [asdict(log) for log in session.log_sequence],
                "timeline": session.investigation_timeline,
                "root_cause": session.root_cause_summary,
                "test_failures": [asdict(t) for t in session.test_outputs],
            }
            data.append(entry)

        # Write to file with nice formatting
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2, default=str)  # default=str handles datetime objects

    def export_to_jsonl(self, sessions: List[SyntheticDebugSession], output_path: Path):
        """
        Export to JSONL format (one JSON object per line).
        JSONL is better for large datasets and streaming processing.
        """
        with open(output_path, "w") as f:
            for session in sessions:
                # Create a simplified entry for each session
                entry = {
                    "bug_id": f"{session.bug_info.project}_{session.bug_info.bug_id}",
                    "project": session.bug_info.project,
                    "logs": [asdict(log) for log in session.log_sequence],
                    "timeline": session.investigation_timeline,
                    "root_cause": session.root_cause_summary,
                }
                # Write as single line of JSON
                f.write(json.dumps(entry, default=str) + "\n")
