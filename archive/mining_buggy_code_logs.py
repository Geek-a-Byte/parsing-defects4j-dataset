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


class Defects4JManager:
    """
    Manages all interactions with the Defects4J command-line tool.
    This class runs defects4j commands and parses their output.
    """

    def __init__(self, defects4j_home: str = None):
        """
        Initialize the manager.
        defects4j_home: Path to Defects4J installation (optional)
        """
        self.defects4j_home = defects4j_home or "/path/to/defects4j"
        # Get list of all available projects when we start
        self.projects = self.get_all_projects()

    def get_all_projects(self) -> List[str]:
        """
        Get list of all projects available in Defects4J.
        Runs 'defects4j pids' command which returns project IDs.
        """
        try:
            # Run the defects4j command to get project IDs
            cmd = "defects4j pids"
            result = subprocess.run(
                cmd, 
                shell=True,  # Run through shell
                capture_output=True,  # Capture stdout and stderr
                text=True,  # Return as string, not bytes
                check=True  # Raise exception if command fails
            )
            # Parse output: each line is a project name
            projects = result.stdout.strip().split("\n")
            # Remove empty lines
            projects = [p.strip() for p in projects if p.strip()]
            print(f"Found {len(projects)} Defects4J projects: {', '.join(projects)}")
            return projects
        except subprocess.CalledProcessError as e:
            # If command fails, use hardcoded list as fallback
            print(f"Error getting projects: {e}")
            print("Falling back to default project list")
            return ["Chart", "Closure", "Lang", "Math", "Mockito", "Time"]

    def get_bug_info(self, project: str, bug_id: str) -> Defects4JBug:
        """
        Get detailed information about a specific bug.
        
        Args:
            project: Project name (e.g., "Lang")
            bug_id: Bug identifier (e.g., "1")
        
        Returns:
            Defects4JBug object with all bug information
        """
        # Run 'defects4j info' command to get bug details
        cmd = f"defects4j info -p {project} -b {bug_id}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

        # Parse the text output into structured data
        info = self._parse_bug_info(result.stdout)
        info["project"] = project
        info["bug_id"] = bug_id

        # Create and return bug object
        return Defects4JBug(**info)

    def _parse_bug_info(self, info_output: str) -> Dict:
        """
        Parse the text output from 'defects4j info' command.
        This extracts structured data from human-readable text.
        
        The output looks like:
        Root cause in triggering tests:
          - org.apache.TestClass::testMethod
        Bug report url: http://...
        List of modified sources:
          - org/apache/SomeClass.java
        """
        info = {}

        # REGEX EXPLANATION:
        # r"..." means raw string (backslashes are literal)
        # \s* means zero or more whitespace characters
        # \n means newline
        # (?:...) is non-capturing group
        # ^ means start of line
        # + means one or more
        # re.MULTILINE makes ^ match start of each line

        # Find triggering tests section
        # This regex looks for "Root cause in triggering tests:" followed by
        # indented lines (which contain the test names)
        tests_match = re.search(
            r"Root cause in triggering tests:\s*\n((?:^[ \t].*\n)+)",
            info_output,
            re.MULTILINE,
        )

        if tests_match:
            # Debug output to see what we found
            print("Triggering tests block:\n" + tests_match.group(1).rstrip())
            # Extract lines that start with a dash (test names)
            # This finds all lines like "  - TestName"
            tests = re.findall(r"^\s*-\s*(.+)$", tests_match.group(1), re.MULTILINE)
            print("Parsed triggering tests:", tests)
            info["triggering_tests"] = tests
        else:
            print("No triggering tests found")
            info["triggering_tests"] = []

        # Find bug report URL (simpler regex)
        url_match = re.search(r"Bug report url:\s*(.+)", info_output)
        info["bug_report_url"] = url_match.group(1) if url_match else ""
        
        # Find modified source files
        sources_match = re.search(
            r"List of modified sources:\s*\n((?:^[ \t].*\n)+)",
            info_output,
            re.MULTILINE,
        )
        if sources_match:
            sources_block = sources_match.group(1)
            print("Modified sources block:\n" + sources_block.rstrip())
            # Extract file names after dashes
            sources = re.findall(r"^\s*-\s*(.+)$", sources_block, re.MULTILINE)
            print("Parsed modified sources:", sources)
            info["modified_classes"] = sources
        else:
            info["modified_classes"] = []

        info["patch"] = ""  # Will be filled later by export_patch method

        return info

    def checkout_bug(
        self, project: str, bug_id: str, work_dir: Path, version: str = "b"
    ) -> Path:
        """
        Download the source code for a specific bug version.
        
        Args:
            project: Project name
            bug_id: Bug identifier
            work_dir: Directory to store the code
            version: "b" for buggy version, "f" for fixed version
        
        Returns:
            Path where the code was downloaded
        """
        # Create directory name like "Lang_1_b" for buggy version of Lang bug #1
        checkout_path = work_dir / f"{project}_{bug_id}_{version}"
        checkout_path.mkdir(parents=True, exist_ok=True)

        # Run defects4j checkout command
        cmd = f"defects4j checkout -p {project} -v {bug_id}{version} -w {checkout_path}"
        subprocess.run(cmd, shell=True, check=True)

        return checkout_path

    def run_tests(
        self, checkout_path: Path, specific_tests: List[str] = None
    ) -> List[TestOutput]:
        """
        Run tests on the checked-out code and capture results.
        
        Args:
            checkout_path: Where the code is located
            specific_tests: Optional list of specific tests to run
        
        Returns:
            List of TestOutput objects with results
        """
        outputs = []

        if specific_tests:
            # Run only the specified tests
            for test in specific_tests:
                output = self._run_single_test(checkout_path, test)
                if output:
                    outputs.append(output)
        else:
            # Run all tests using defects4j test command
            cmd = f"cd {checkout_path} && defects4j test"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            outputs = self._parse_test_output(result.stdout, result.stderr)

        # Defects4J creates a "failing_tests" file with detailed error info
        failing_tests_file = checkout_path / "failing_tests"
        if failing_tests_file.exists():
            # Add detailed error messages and stack traces to our test outputs
            outputs = self._enrich_with_failure_details(outputs, failing_tests_file)

        return outputs

    def _run_single_test(
        self, checkout_path: Path, test_name: str
    ) -> Optional[TestOutput]:
        """
        Run a single test and capture its output.
        
        Args:
            checkout_path: Where the code is located
            test_name: Name of the test to run
        
        Returns:
            TestOutput object with results, or None if test couldn't run
        """
        # Run specific test using -t flag
        cmd = f"cd {checkout_path} && defects4j test -t {test_name}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

        # Parse the result
        output = self._parse_single_test_result(test_name, result.stdout, result.stderr)

        # Try to get more detailed failure info from Defects4J output files
        failing_tests_file = checkout_path / "failing_tests"
        if failing_tests_file.exists():
            with open(failing_tests_file, "r") as f:
                failing_content = f.read()
                # If this test failed, extract the error message
                if test_name in failing_content:
                    if not output.error_message:
                        output.error_message = self._extract_error_from_failing_tests(
                            failing_content, test_name
                        )

        return output

    def _parse_test_output(self, stdout: str, stderr: str) -> List[TestOutput]:
        """
        Parse the output from running multiple tests.
        Defects4J output format shows failing tests with "  - " prefix.
        """
        outputs = []

        # Debug: show what we're parsing
        print("Defects4J test output:\n" + stdout)
        
        # Find all lines that start with "  - " (these are test names)
        # The regex looks for lines starting with two spaces, dash, space, then test name
        failing_match = re.findall(r"^  - ([a-zA-Z0-9_.$:]+)$", stdout, re.MULTILINE)

        # Create TestOutput object for each failing test
        for test_name in failing_match:
            output = TestOutput(
                test_name=test_name,
                status="FAIL",
                error_message=None,  # Will be filled later
                stack_trace=None,  # Will be filled later
                execution_time=0.0,
                timestamp=datetime.now(),
            )
            outputs.append(output)

        return outputs

    def _parse_single_test_result(
        self, test_name: str, stdout: str, stderr: str
    ) -> TestOutput:
        """
        Parse the result of running a single test.
        Determines if test passed or failed based on output.
        """
        # If output says "Failing tests: 0", then all tests passed
        passed = "Failing tests: 0" in stdout

        return TestOutput(
            test_name=test_name,
            status="PASS" if passed else "FAIL",
            error_message=None,  # Will be filled by _enrich_with_failure_details
            stack_trace=None,  # Will be filled by _enrich_with_failure_details
            execution_time=0.0,
            timestamp=datetime.now(),
        )

    def _enrich_with_failure_details(
        self, outputs: List[TestOutput], failing_tests_file: Path
    ) -> List[TestOutput]:
        """
        Add detailed error messages and stack traces from the failing_tests file.
        This file contains the actual Java exceptions and stack traces.
        """
        try:
            # Read the file with detailed failure information
            with open(failing_tests_file, "r") as f:
                failing_content = f.read()

            # Debug: show what's in the file
            print(f"\n--- Content of failing_tests file ---")
            print(failing_content[:1000])  # Show first 1000 characters
            print("--- End of failing_tests preview ---\n")

            # For each failing test, extract its error details
            for output in outputs:
                if output.status == "FAIL":
                    # Extract detailed error and stack trace
                    if not output.error_message:
                        output.error_message = self._extract_error_from_failing_tests(
                            failing_content, output.test_name
                        )
        except Exception as e:
            # If something goes wrong, log it but continue
            print(f"Warning: Could not enrich failure details: {e}")
            import traceback
            traceback.print_exc()

        return outputs

    def _extract_error_from_failing_tests(
        self, content: str, test_name: str
    ) -> Optional[str]:
        """
        Extract the complete error message (exception + stack trace) for a specific test.

        The failing_tests file format looks like:
        --- test.class.name::testMethod
        ExceptionType: error message
            at stacktrace line 1
            at stacktrace line 2
            ...
        --- next.test::method
        ...
        """
        # Defects4J sometimes uses different formats for test names
        # Try multiple variations to find the test
        test_name_variants = [
            test_name,  # Original: org.Foo::testBar
            test_name.replace("::", "."),  # Alternative: org.Foo.testBar
            test_name.split("::")[0] if "::" in test_name else test_name,  # Just class: org.Foo
        ]

        for variant in test_name_variants:
            # Look for header line starting with "---" followed by test name
            # re.escape() escapes special regex characters in the test name
            header_re = rf"(?m)^---\s*{re.escape(variant)}(?:\s+(.*))?$"
            header_match = re.search(header_re, content)

            if not header_match:
                continue  # Try next variant

            # Sometimes there's extra text on the header line
            header_extra = header_match.group(1) or ""

            # Find where this test's section starts (right after header)
            start_pos = header_match.end()

            # Find where next test section starts (next "---" line)
            next_header = re.search(r"(?m)^---\s", content[start_pos:])
            # If found, that's where this section ends; otherwise, go to end of file
            end_pos = start_pos + next_header.start() if next_header else len(content)

            # Extract the error section between headers
            rest_block = content[start_pos:end_pos].lstrip("\r\n").rstrip()

            # Combine header extra (if any) with the rest
            if header_extra:
                error_section = header_extra.rstrip() + "\n" + rest_block
            else:
                error_section = rest_block

            if error_section.strip():
                return error_section

        # If we couldn't find the test with any variant
        return None

    def export_patch(self, project: str, bug_id: str) -> str:
        """
        Export the patch (code changes) that fixed the bug.
        This shows what was changed between buggy and fixed versions.
        """
        # Try to get code changes
        cmd = f"defects4j export -p code.changes -w /tmp/d4j_{project}_{bug_id}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

        # Alternative: try to get git diff format
        cmd_diff = f"defects4j export -p diff -w /tmp/d4j_{project}_{bug_id}"
        result_diff = subprocess.run(
            cmd_diff, shell=True, capture_output=True, text=True
        )

        # Return whichever command succeeded
        return result_diff.stdout if result_diff.returncode == 0 else result.stdout

    def get_all_bugs(self, project: str) -> List[str]:
        """
        Get list of all bug IDs for a project.
        Each project has multiple bugs numbered 1, 2, 3, etc.
        """
        cmd = f"defects4j bids -p {project}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

        # Each line is a bug ID
        return result.stdout.strip().split("\n")


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
    output_dir = Path("./synthetic_logs")
    output_dir.mkdir(exist_ok=True)

    # === INITIALIZE COMPONENTS ===
    d4j = Defects4JManager()  # Handles Defects4J operations
    generator = SyntheticLogGenerator()  # Creates synthetic logs
    exporter = DatasetExporter()  # Exports data to files

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
    project = "Lang"
    print(f"\nProcessing {project} project...")

    # Get list of all bug IDs for this project
    bug_ids = d4j.get_all_bugs(project)[:5]  # Take first 5 bugs only

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

            # Step 4: Get the patch that fixed the bug
            bug_info.patch = d4j.export_patch(project, bug_id)

            # Step 5: Generate synthetic debug session
            session = generator.generate_debug_session(bug_info, test_outputs)
            sessions.append(session)

            # Print summary
            print(f"  Generated {len(session.log_sequence)} log entries")
            print(f"  Root cause: {session.root_cause_summary}")

        except Exception as e:
            # If something goes wrong, log it and continue with next bug
            print(f"  Error processing {project}-{bug_id}: {e}")
            import traceback
            traceback.print_exc()
            continue

    # === EXPORT RESULTS ===
    print(f"\nExporting {len(sessions)} debug sessions...")
    exporter.export_to_json(sessions, output_dir / "debug_sessions.json")
    exporter.export_to_jsonl(sessions, output_dir / "debug_sessions.jsonl")

    print(f"Done! Output saved to {output_dir}")

    # === SHOW SAMPLE OUTPUT ===
    if sessions:
        print("\n" + "=" * 80)
        print("Sample Debug Session:")
        print("=" * 80)
        sample = sessions[0]  # Show first session as example
        print(f"Bug: {sample.bug_info.project}-{sample.bug_info.bug_id}")
        
        print(f"\nTimeline:")
        for step in sample.investigation_timeline:
            print(f"  - {step}")
            
        print(f"\nLog Sample (first 5 entries):")
        for log in sample.log_sequence[:5]:
            print(
                f"  [{log.timestamp}] {log.level:8} | {log.source:12} | {log.message}"
            )


# This is the entry point when running the script
if __name__ == "__main__":
    main()
