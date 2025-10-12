import json
import subprocess
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
import xml.etree.ElementTree as ET

from utils import Defects4JBug,TestOutput


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
            --> exception details (should be ignored)
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
            # FIXED: Exclude lines that start with "-->" (exception details)
            tests = re.findall(r"^\s*-\s+(?!->)(.+)$", tests_match.group(1), re.MULTILINE)
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
            # failing_tests_file = checkout_path / "failing_tests"
            # if failing_tests_file.exists():
            #     # Add detailed error messages and stack traces to our test outputs
            #     outputs = self._enrich_with_failure_details(outputs, failing_tests_file)

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
                    print(f"Detailed error for {test_name}:")
                    print(output.error_message)

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
