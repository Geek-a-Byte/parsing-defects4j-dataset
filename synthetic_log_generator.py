import json
import subprocess
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
import xml.etree.ElementTree as ET

from utils import Defects4JBug, LogEntry, SyntheticDebugSession, TestOutput

class SyntheticLogGenerator:
    """
    Generates realistic debugging logs from Defects4J data.
    Creates synthetic logs that simulate a developer debugging the issue.
    """

    def __init__(self):
        # Base timestamp for generating sequential log entries
        self.base_time = datetime.now()

    def generate_debug_session(
        self, bug: Defects4JBug, test_outputs: List[TestOutput]
    ) -> SyntheticDebugSession:
        """
        Generate a complete debugging session with synthetic logs.
        This simulates the entire process of finding and fixing a bug.
        
        The session has 5 phases:
        1. Setup - Initialize and run tests
        2. Failure - Analyze test failures
        3. Investigation - Examine the code
        4. Discovery - Find the root cause
        5. Resolution - Apply and verify the fix
        """

        log_sequence = []  # All log entries
        investigation_timeline = []  # Human-readable steps

        # Phase 1: Initial setup and test execution
        phase1_logs, phase1_steps = self._generate_setup_phase(bug, test_outputs)
        log_sequence.extend(phase1_logs)
        investigation_timeline.extend(phase1_steps)

        # Phase 2: Test failures and error analysis
        phase2_logs, phase2_steps = self._generate_failure_phase(bug, test_outputs)
        log_sequence.extend(phase2_logs)
        investigation_timeline.extend(phase2_steps)

        # Phase 3: Code investigation
        phase3_logs, phase3_steps = self._generate_investigation_phase(bug)
        log_sequence.extend(phase3_logs)
        investigation_timeline.extend(phase3_steps)

        # Phase 4: Root cause identification
        phase4_logs, phase4_steps = self._generate_discovery_phase(bug)
        log_sequence.extend(phase4_logs)
        investigation_timeline.extend(phase4_steps)

        # Phase 5: Fix application and verification
        phase5_logs, phase5_steps = self._generate_resolution_phase(bug)
        log_sequence.extend(phase5_logs)
        investigation_timeline.extend(phase5_steps)

        # Generate a summary of what caused the bug
        root_cause = self._generate_root_cause_summary(bug, test_outputs)

        return SyntheticDebugSession(
            bug_info=bug,
            test_outputs=test_outputs,
            log_sequence=log_sequence,
            investigation_timeline=investigation_timeline,
            root_cause_summary=root_cause,
        )

    def _generate_setup_phase(
        self, bug: Defects4JBug, test_outputs: List[TestOutput]
    ) -> tuple:
        """
        Generate logs for the setup phase.
        This simulates building the project and preparing to run tests.
        """
        logs = []
        steps = []
        t = self.base_time  # Current timestamp

        # Log: Building the project
        logs.append(
            LogEntry(
                timestamp=t.isoformat(),  # Convert to string like "2024-01-15T10:30:00"
                level="INFO",
                source="build",
                message=f"Building {bug.project} project (bug {bug.bug_id})",
                metadata={"project": bug.project, "bug_id": bug.bug_id},
            )
        )
        steps.append(f"Started investigating {bug.project} bug #{bug.bug_id}")

        # Advance time by 5 seconds for next log
        t += timedelta(seconds=5)
        
        # Log: Running tests
        logs.append(
            LogEntry(
                timestamp=t.isoformat(),
                level="INFO",
                source="test_runner",
                message=f"Running test suite ({len(test_outputs)} tests)",
                metadata={"test_count": len(test_outputs)},
            )
        )
        steps.append("Executed test suite to reproduce issue")

        return logs, steps

    def _generate_failure_phase(
        self, bug: Defects4JBug, test_outputs: List[TestOutput]
    ) -> tuple:
        """
        Generate logs for test failures.
        This uses the REAL test output from Defects4J.
        """
        logs = []
        steps = []
        t = self.base_time + timedelta(seconds=10)  # Start 10 seconds after base time

        # Process each test that failed
        for i, test_output in enumerate(test_outputs):
            if test_output.status == "FAIL":
                t += timedelta(seconds=2)

                # Log the test failure
                logs.append(
                    LogEntry(
                        timestamp=t.isoformat(),
                        level="ERROR",
                        source="test",
                        message=f"Test failed: {test_output.test_name}",
                        metadata={
                            "test_name": test_output.test_name,
                            "error": test_output.error_message,
                            "execution_time": test_output.execution_time,
                        },
                    )
                )

                # Log the stack trace if available
                if test_output.stack_trace:
                    t += timedelta(seconds=1)
                    logs.append(
                        LogEntry(
                            timestamp=t.isoformat(),
                            level="ERROR",
                            source="test",
                            message=f"Stack trace for {test_output.test_name}",
                            metadata={"stack_trace": test_output.stack_trace[:500]},  # First 500 chars
                        )
                    )

                steps.append(f"Identified failing test: {test_output.test_name}")

        return logs, steps

    def _generate_investigation_phase(self, bug: Defects4JBug) -> tuple:
        """
        Generate logs for code investigation.
        Simulates a developer examining the code to understand the problem.
        """
        logs = []
        steps = []
        t = self.base_time + timedelta(minutes=1)  # 1 minute into debugging

        logs.append(
            LogEntry(
                timestamp=t.isoformat(),
                level="DEBUG",
                source="debugger",
                message="Starting code investigation",
                metadata={"modified_classes": bug.modified_classes},
            )
        )
        steps.append("Began examining modified classes")

        # Simulate investigating each modified class
        for i, class_name in enumerate(bug.modified_classes[:3]):  # First 3 classes
            t += timedelta(seconds=10)
            logs.append(
                LogEntry(
                    timestamp=t.isoformat(),
                    level="DEBUG",
                    source="debugger",
                    message=f"Examining class: {class_name}",
                    metadata={
                        "class": class_name,
                        "methods_checked": ["method1", "method2"],  # Simulated method names
                    },
                )
            )
            steps.append(f"Analyzed {class_name}")

        return logs, steps

    def _generate_discovery_phase(self, bug: Defects4JBug) -> tuple:
        """
        Generate logs for discovering the root cause.
        This is where the developer figures out what's wrong.
        """
        logs = []
        steps = []
        t = self.base_time + timedelta(minutes=2)  # 2 minutes into debugging

        # Try to guess what type of bug it is based on the patch
        root_cause_hint = self._infer_root_cause_from_patch(bug.patch)

        logs.append(
            LogEntry(
                timestamp=t.isoformat(),
                level="INFO",
                source="debugger",
                message=f"Root cause identified: {root_cause_hint}",
                metadata={"bug_url": bug.bug_report_url},
            )
        )
        steps.append(f"Discovered root cause: {root_cause_hint}")

        t += timedelta(seconds=5)
        logs.append(
            LogEntry(
                timestamp=t.isoformat(),
                level="DEBUG",
                source="debugger",
                message="Analyzing patch differences",
                metadata={"modified_files": len(bug.modified_classes)},
            )
        )
        steps.append("Reviewed patch to understand fix")

        return logs, steps

    def _generate_resolution_phase(self, bug: Defects4JBug) -> tuple:
        """
        Generate logs for fixing the bug.
        Simulates applying the patch and verifying it works.
        """
        logs = []
        steps = []
        t = self.base_time + timedelta(minutes=3)  # 3 minutes into debugging

        logs.append(
            LogEntry(
                timestamp=t.isoformat(),
                level="INFO",
                source="vcs",  # Version control system
                message="Applying patch to fix bug",
                metadata={"bug_id": bug.bug_id},
            )
        )
        steps.append("Applied patch from fixed version")

        t += timedelta(seconds=10)
        logs.append(
            LogEntry(
                timestamp=t.isoformat(),
                level="INFO",
                source="test_runner",
                message="Re-running tests after fix",
                metadata={"expected_result": "PASS"},
            )
        )
        steps.append("Verified fix by re-running tests")

        t += timedelta(seconds=5)
        logs.append(
            LogEntry(
                timestamp=t.isoformat(),
                level="INFO",
                source="test",
                message="All tests passing after fix",
                metadata={"status": "SUCCESS"},
            )
        )
        steps.append("Confirmed all tests now pass")

        return logs, steps

    def _infer_root_cause_from_patch(self, patch: str) -> str:
        """
        Try to guess what type of bug it was based on the patch content.
        This uses simple heuristics to categorize the bug.
        """
        if not patch:
            return "Logic error in implementation"

        # Look for keywords in the patch to guess bug type
        if "null" in patch.lower():
            return "Null pointer handling issue"
        elif "bound" in patch.lower() or "index" in patch.lower():
            return "Array bounds or indexing error"
        elif "assert" in patch.lower():
            return "Assertion or validation error"
        elif "==" in patch or "!=" in patch:
            return "Comparison or equality check error"
        else:
            return "Logic error in implementation"

    def _generate_root_cause_summary(
        self, bug: Defects4JBug, test_outputs: List[TestOutput]
    ) -> str:
        """
        Generate a human-readable summary of what caused the bug.
        This combines information from tests and bug details.
        """
        # Count how many tests failed
        failed_tests = [t for t in test_outputs if t.status == "FAIL"]

        # Build summary string
        summary = f"Bug in {bug.project} (#{bug.bug_id}): "
        summary += f"{len(failed_tests)} test(s) failed. "
        summary += f"Root cause located in {', '.join(bug.modified_classes[:2])}. "

        # Add error message if available
        if failed_tests and failed_tests[0].error_message:
            summary += f"Error: {failed_tests[0].error_message[:100]}..."

        return summary
