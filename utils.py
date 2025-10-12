import json
import subprocess
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
import xml.etree.ElementTree as ET


# DATACLASSES: These are like templates that define what information we store
# @dataclass automatically creates __init__, __repr__, and other methods

@dataclass
class Defects4JBug:
    """
    Represents a bug from Defects4J database.
    This stores all the information about a single bug.
    """
    project: str  # Which project (e.g., "Math", "Lang", "Chart")
    bug_id: str  # Unique identifier for this bug (e.g., "1", "2", "3")
    triggering_tests: List[str]  # Tests that fail because of this bug
    bug_report_url: str  # Link to original bug report (if available)
    patch: str  # The actual code changes that fixed the bug
    modified_classes: List[str]  # Which Java classes were changed to fix the bug
    checkout_path: Optional[Path] = None  # Where the code is stored on disk


@dataclass
class TestOutput:
    """
    Represents the result of running a single test.
    When we run tests, each one either passes or fails.
    """
    test_name: str  # Full name of the test (e.g., "org.apache.Math.TestAddition")
    status: str  # PASS, FAIL, or ERROR
    error_message: Optional[str]  # What went wrong (if test failed)
    stack_trace: Optional[str]  # Detailed error trace showing where code failed
    execution_time: float  # How long the test took to run (in seconds)
    timestamp: datetime  # When the test was run


@dataclass
class LogEntry:
    """
    Represents a single log entry (like a line in a log file).
    We create synthetic logs that look like real debugging sessions.
    """
    timestamp: str  # When this log was created (ISO format like "2024-01-15T10:30:00")
    level: str  # Severity: DEBUG, INFO, WARNING, ERROR
    source: str  # Which component generated this log (e.g., "test_runner", "debugger")
    message: str  # The actual log message
    metadata: Dict[str, Any] = None  # Additional structured data


@dataclass
class SyntheticDebugSession:
    """
    Complete debugging session with all information combined.
    This represents a full investigation of one bug from start to finish.
    """
    bug_info: Defects4JBug  # All information about the bug
    test_outputs: List[TestOutput]  # Results from running tests
    log_sequence: List[LogEntry]  # Synthetic logs we generated
    investigation_timeline: List[str]  # Human-readable steps of investigation
    root_cause_summary: str  # Brief explanation of what caused the bug
