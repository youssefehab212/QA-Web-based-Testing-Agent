"""
Verification Service
Handles REAL test execution with video evidence and critique-based refactoring

Features:
1. Actual test execution using pytest
2. Video recording of test runs for evidence
3. Critique-based refactoring loop
"""

import json
import re
import os
import subprocess
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Callable, Optional, Generator


def log(message: str, level: str = "INFO"):
    """Print a formatted log message with timestamp"""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] [{level}] [Verification] {message}")


# Directory paths
BASE_DIR = Path(__file__).parent.parent
TESTS_DIR = BASE_DIR / 'tests'
EVIDENCE_DIR = BASE_DIR / 'evidence'


class VerificationService:
    """Service for verifying test code with real execution and video evidence"""
    
    @staticmethod
    def ensure_evidence_dir() -> Path:
        """Ensure the evidence directory exists"""
        if not EVIDENCE_DIR.exists():
            EVIDENCE_DIR.mkdir(parents=True)
            log(f"Created evidence directory: {EVIDENCE_DIR}")
        return EVIDENCE_DIR
    
    @staticmethod
    def generate_video_config(force: bool = False) -> str:
        """
        Generate a conftest.py that enables video recording and step-by-step logging for Playwright tests
        Only regenerates if the file doesn't exist or force=True
        
        Args:
            force: If True, regenerate even if file exists
        
        Returns:
            Path to the conftest file
        """
        conftest_path = TESTS_DIR / 'conftest.py'
        
        # Check if conftest.py already exists and has our logging setup
        if conftest_path.exists() and not force:
            try:
                existing_content = conftest_path.read_text(encoding='utf-8')
                # Check if it already has our video recording AND logging setup
                if 'record_video_dir' in existing_content and 'EVIDENCE_DIR' in existing_content and 'PlaywrightLogger' in existing_content:
                    log(f"conftest.py already configured for video recording and logging, skipping regeneration")
                    return str(conftest_path)
            except Exception:
                pass  # If we can't read it, regenerate
        
        evidence_dir = VerificationService.ensure_evidence_dir()
        
        conftest_content = f'''"""
conftest.py for video recording and step-by-step logging
All tests in a session share one log file and one video directory
"""
import pytest
import json
import logging
import time
import os
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright, Page

EVIDENCE_DIR = Path(r"{evidence_dir}")

# Read headless mode from environment variable (default to True)
HEADLESS_MODE = os.environ.get('PLAYWRIGHT_HEADLESS', 'true').lower() == 'true'

# Session-level variables - created once per test run, shared by all tests
SESSION_TIMESTAMP = datetime.now().strftime('%Y%m%d_%H%M%S')
SESSION_VIDEO_DIR = EVIDENCE_DIR / SESSION_TIMESTAMP
SESSION_LOG_FILE = EVIDENCE_DIR / f"test_execution_{{SESSION_TIMESTAMP}}.log"
SESSION_REPORT_FILE = EVIDENCE_DIR / f"report_{{SESSION_TIMESTAMP}}.json"

# Track test results for the evidence report
SESSION_TEST_RESULTS = []
SESSION_START_TIME = datetime.now()

# Ensure directories exist at module load
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
SESSION_VIDEO_DIR.mkdir(parents=True, exist_ok=True)

# Configure session-level file handler (one log file for all tests)
file_handler = logging.FileHandler(SESSION_LOG_FILE, mode='w', encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))

logger = logging.getLogger("playwright_test")
logger.setLevel(logging.DEBUG)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

logger.info(f"========== TEST SESSION STARTED ==========")
logger.info(f"Session timestamp: {{SESSION_TIMESTAMP}}")
logger.info(f"Log file: {{SESSION_LOG_FILE}}")
logger.info(f"Video directory: {{SESSION_VIDEO_DIR}}")
logger.info("")


class PlaywrightLogger:
    """Wrapper to log Playwright page actions step-by-step. Uses session-level logger."""
    
    def __init__(self, page: Page, test_name: str):
        self._page = page
        self._test_name = test_name
        self._step_count = 0
        
        # Log test start (uses session-level file handler)
        logger.info("")
        logger.info(f"---------- TEST: {{test_name}} ----------")
        logger.info(f"Starting test execution")
    
    def _log(self, message: str, level: str = "INFO"):
        """Log a message"""
        if level == "ERROR":
            logger.error(message)
        elif level == "WARNING":
            logger.warning(message)
        else:
            logger.info(message)
    
    def _step(self, action: str, details: str = ""):
        """Log a test step"""
        self._step_count += 1
        msg = f"  Step {{self._step_count}}: {{action}}"
        if details:
            msg += f" | {{details}}"
        self._log(msg)
    
    def goto(self, url: str, **kwargs):
        self._step("NAVIGATE", f"URL: {{url}}")
        result = self._page.goto(url, **kwargs)
        self._log(f"  -> Page loaded: {{self._page.title()}}")
        return result
    
    def click(self, selector, **kwargs):
        self._step("CLICK", f"Selector: {{selector}}")
        return self._page.click(selector, **kwargs)
    
    def fill(self, selector, value: str, **kwargs):
        self._step("FILL", f"Selector: {{selector}} | Value: '{{value[:50]}}...' " if len(value) > 50 else f"Selector: {{selector}} | Value: '{{value}}'")
        return self._page.fill(selector, value, **kwargs)
    
    def type(self, selector, text: str, **kwargs):
        self._step("TYPE", f"Selector: {{selector}} | Text: '{{text[:50]}}...' " if len(text) > 50 else f"Selector: {{selector}} | Text: '{{text}}'")
        return self._page.type(selector, text, **kwargs)
    
    def press(self, selector, key: str, **kwargs):
        self._step("PRESS KEY", f"Selector: {{selector}} | Key: {{key}}")
        return self._page.press(selector, key, **kwargs)
    
    def check(self, selector, **kwargs):
        self._step("CHECK", f"Selector: {{selector}}")
        return self._page.check(selector, **kwargs)
    
    def uncheck(self, selector, **kwargs):
        self._step("UNCHECK", f"Selector: {{selector}}")
        return self._page.uncheck(selector, **kwargs)
    
    def select_option(self, selector, **kwargs):
        self._step("SELECT OPTION", f"Selector: {{selector}} | Options: {{kwargs}}")
        return self._page.select_option(selector, **kwargs)
    
    def hover(self, selector, **kwargs):
        self._step("HOVER", f"Selector: {{selector}}")
        return self._page.hover(selector, **kwargs)
    
    def wait_for_selector(self, selector, **kwargs):
        self._step("WAIT FOR", f"Selector: {{selector}}")
        return self._page.wait_for_selector(selector, **kwargs)
    
    def wait_for_load_state(self, state: str = "load", **kwargs):
        self._step("WAIT FOR LOAD STATE", f"State: {{state}}")
        return self._page.wait_for_load_state(state, **kwargs)
    
    def wait_for_url(self, url, **kwargs):
        self._step("WAIT FOR URL", f"URL pattern: {{url}}")
        return self._page.wait_for_url(url, **kwargs)
    
    def screenshot(self, **kwargs):
        path = kwargs.get('path', 'screenshot.png')
        self._step("SCREENSHOT", f"Path: {{path}}")
        return self._page.screenshot(**kwargs)
    
    def locator(self, selector, **kwargs):
        self._log(f"  Locating: {{selector}}")
        return self._page.locator(selector, **kwargs)
    
    def get_by_role(self, role, **kwargs):
        self._log(f"  Locating by role: {{role}} {{kwargs}}")
        return self._page.get_by_role(role, **kwargs)
    
    def get_by_text(self, text, **kwargs):
        self._log(f"  Locating by text: '{{text}}'")
        return self._page.get_by_text(text, **kwargs)
    
    def get_by_label(self, label, **kwargs):
        self._log(f"  Locating by label: '{{label}}'")
        return self._page.get_by_label(label, **kwargs)
    
    def get_by_placeholder(self, placeholder, **kwargs):
        self._log(f"  Locating by placeholder: '{{placeholder}}'")
        return self._page.get_by_placeholder(placeholder, **kwargs)
    
    def get_by_test_id(self, test_id, **kwargs):
        self._log(f"  Locating by test-id: '{{test_id}}'")
        return self._page.get_by_test_id(test_id, **kwargs)
    
    def evaluate(self, expression, **kwargs):
        self._step("EVALUATE JS", f"Expression: {{expression[:100]}}..." if len(str(expression)) > 100 else f"Expression: {{expression}}")
        return self._page.evaluate(expression, **kwargs)
    
    def content(self):
        self._log("  Getting page content")
        return self._page.content()
    
    @property
    def url(self):
        return self._page.url
    
    def title(self):
        return self._page.title()
    
    def close(self):
        self._log(f"Closing page")
        return self._page.close()
    
    def cleanup(self, passed: bool = True):
        """Log test completion - no file handler management needed (session-level)"""
        status = "PASSED" if passed else "FAILED"
        self._log(f"---------- {{status}}: {{self._test_name}} ({{self._step_count}} steps) ----------")
    
    def __getattr__(self, name):
        """Forward any other attributes to the underlying page"""
        return getattr(self._page, name)


@pytest.fixture(scope="function")
def page(request):
    """Fixture that provides a page with video recording and step-by-step logging enabled"""
    with sync_playwright() as p:
        test_name = request.node.name
        
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            record_video_dir=str(SESSION_VIDEO_DIR),
            record_video_size={{"width": 1280, "height": 720}}
        )
        raw_page = context.new_page()
        
        # Wrap page with logging (uses session-level log file)
        logged_page = PlaywrightLogger(raw_page, test_name)
        
        yield logged_page
        
        # Determine actual test result from pytest hook
        passed = True
        if hasattr(request.node, "rep_call"):
            passed = request.node.rep_call.passed
        
        # Log test completion with actual result
        logged_page.cleanup(passed=passed)
        
        # Add delay to ensure video captures the final state
        time.sleep(1.5)
        
        # Close context to save video
        context.close()
        browser.close()
        
        # Rename video file to match test name
        for video_file in SESSION_VIDEO_DIR.glob("*.webm"):
            # Only rename if it's a temp file (not already named)
            if not video_file.stem.startswith("test_"):
                new_name = SESSION_VIDEO_DIR / f"{{test_name}}.webm"
                try:
                    video_file.rename(new_name)
                    logger.info(f"Video saved: {{new_name}}")
                except Exception:
                    pass
                break


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Store test result on the request node and collect results for evidence report"""
    outcome = yield
    rep = outcome.get_result()
    # Store the result for each phase (setup, call, teardown)
    setattr(item, f"rep_{{rep.when}}", rep)
    
    # Collect test results during the 'call' phase (actual test execution)
    if rep.when == "call":
        test_result = {{
            "name": item.nodeid,
            "status": rep.outcome,  # 'passed', 'failed', 'skipped'
            "passed": rep.passed,
            "duration": rep.duration,
            "error": str(rep.longrepr) if rep.failed else None
        }}
        SESSION_TEST_RESULTS.append(test_result)


def pytest_sessionfinish(session, exitstatus):
    """Hook to log session completion and generate JSON evidence report"""
    end_time = datetime.now()
    duration = (end_time - SESSION_START_TIME).total_seconds()
    
    logger.info("")
    logger.info(f"========== TEST SESSION FINISHED ==========")
    logger.info(f"Exit status: {{exitstatus}}")
    logger.info(f"Log file: {{SESSION_LOG_FILE}}")
    logger.info(f"Videos: {{SESSION_VIDEO_DIR}}")
    
    # Collect video files
    video_files = list(SESSION_VIDEO_DIR.glob("*.webm")) if SESSION_VIDEO_DIR.exists() else []
    
    # Calculate test statistics
    passed_count = len([t for t in SESSION_TEST_RESULTS if t.get('passed')])
    failed_count = len([t for t in SESSION_TEST_RESULTS if not t.get('passed')])
    total_count = len(SESSION_TEST_RESULTS)
    
    # Generate evidence report
    report = {{
        "timestamp": end_time.isoformat(),
        "session_timestamp": SESSION_TIMESTAMP,
        "execution": {{
            "success": exitstatus == 0,
            "duration": duration,
            "exit_code": exitstatus
        }},
        "tests": {{
            "total": total_count,
            "passed": passed_count,
            "failed": failed_count,
            "details": SESSION_TEST_RESULTS
        }},
        "evidence": {{
            "video_dir": str(SESSION_VIDEO_DIR),
            "video_files": [str(v) for v in video_files],
            "log_file": str(SESSION_LOG_FILE),
            "evidence_dir": str(EVIDENCE_DIR)
        }}
    }}
    
    # Save report to JSON
    try:
        with open(SESSION_REPORT_FILE, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)
        logger.info(f"Evidence report saved: {{SESSION_REPORT_FILE}}")
    except Exception as e:
        logger.error(f"Failed to save evidence report: {{e}}")
'''
        
        with open(conftest_path, 'w', encoding='utf-8') as f:
            f.write(conftest_content)
        
        log(f"Generated conftest.py with video recording and logging at: {conftest_path}")
        return str(conftest_path)
    
    @staticmethod
    def run_pytest_with_video(test_file: str, headed: bool = False) -> Dict[str, Any]:
        """
        Run pytest on a test file with video recording and logging
        
        Args:
            test_file: Path to the test file
            headed: Whether to run in headed mode (visible browser)
            
        Returns:
            Execution result with stdout, stderr, success status, video paths, and log file
        """
        log(f"========== RUNNING TESTS WITH VIDEO ==========")
        log(f"Test file: {test_file}")
        log(f"Headed mode: {headed}")
        
        # Ensure evidence directory exists
        evidence_dir = VerificationService.ensure_evidence_dir()
        
        # Generate conftest for video recording
        VerificationService.generate_video_config()
        
        # Build pytest command
        # Note: Logging is handled by conftest.py which creates a session-level log file
        cmd = [
            "python", "-m", "pytest",
            test_file,
            "-v",
            "--tb=long",
            "-rA",
            "--capture=tee-sys",
        ]
        
        log(f"Running command: {' '.join(cmd)}")
        log(f"Note: Logging handled by conftest.py (session-level log file)")
        
        # Set environment variable for headless mode
        env = os.environ.copy()
        env['PLAYWRIGHT_HEADLESS'] = 'false' if headed else 'true'
        
        try:
            # Run pytest
            start_time = datetime.now()
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute timeout
                cwd=str(BASE_DIR),
                env=env
            )
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            log(f"Pytest completed in {duration:.2f}s")
            log(f"Return code: {result.returncode}")
            
            # Collect video files and log file (created by conftest.py)
            video_files = list(evidence_dir.rglob("*.webm"))
            log_files = list(evidence_dir.glob("test_execution_*.log"))
            log_file = max(log_files, key=lambda f: f.stat().st_mtime) if log_files else None
            
            log(f"Video files captured: {len(video_files)}")
            log(f"Log file: {log_file}")
            
            # Parse test results from output
            test_results = VerificationService.parse_pytest_output(result.stdout)
            
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.returncode,
                "duration": duration,
                "video_files": [str(v) for v in video_files],
                "log_file": str(log_file) if log_file else None,
                "evidence_dir": str(evidence_dir),
                "test_results": test_results
            }
            
        except subprocess.TimeoutExpired:
            log("Test execution timed out!", "ERROR")
            log_files = list(evidence_dir.glob("test_execution_*.log"))
            log_file = max(log_files, key=lambda f: f.stat().st_mtime) if log_files else None
            return {
                "success": False,
                "error": "Test execution timed out after 5 minutes",
                "stdout": "",
                "stderr": "",
                "return_code": -1,
                "duration": 300,
                "video_files": [],
                "log_file": str(log_file) if log_file else None,
                "evidence_dir": str(evidence_dir),
                "test_results": []
            }
        except Exception as e:
            log(f"Error running tests: {e}", "ERROR")
            log_files = list(evidence_dir.glob("test_execution_*.log"))
            log_file = max(log_files, key=lambda f: f.stat().st_mtime) if log_files else None
            return {
                "success": False,
                "error": str(e),
                "stdout": "",
                "stderr": "",
                "return_code": -1,
                "log_file": str(log_file) if log_file else None,
                "duration": 0,
                "video_files": [],
                "evidence_dir": str(evidence_dir),
                "test_results": []
            }
    
    @staticmethod
    def run_pytest_streaming(test_file: str) -> Generator[Dict[str, Any], None, None]:
        """
        Run pytest and stream test results as they complete.
        Yields events for each test result in real-time.
        
        Args:
            test_file: Path to the test file
            
        Yields:
            Dict with event type and data (test_start, test_result, complete)
        """
        log(f"========== STREAMING TEST EXECUTION ==========")
        log(f"Test file: {test_file}")
        
        evidence_dir = VerificationService.ensure_evidence_dir()
        VerificationService.generate_video_config()
        
        cmd = [
            "python", "-m", "pytest",
            test_file,
            "-v",
            "--tb=short",
            "-rA",
        ]
        
        log(f"Running command: {' '.join(cmd)}")
        
        # Yield start event
        yield {"event": "start", "data": {"test_file": test_file}}
        
        start_time = datetime.now()
        stdout_lines = []
        test_pattern = re.compile(r'(test_\w+\.py::test_\w+)\s+(PASSED|FAILED|SKIPPED|ERROR)')
        tests_seen = set()
        
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,  # Line buffered
                cwd=str(BASE_DIR)
            )
            
            for line in iter(process.stdout.readline, ''):
                stdout_lines.append(line)
                log(f"[pytest] {line.rstrip()}")
                
                # Check if this line contains a test result
                match = test_pattern.search(line)
                if match:
                    test_name = match.group(1)
                    status = match.group(2)
                    
                    # Only yield if we haven't seen this test yet
                    if test_name not in tests_seen:
                        tests_seen.add(test_name)
                        
                        # Yield test result event
                        yield {
                            "event": "test_result",
                            "data": {
                                "name": test_name,
                                "status": status.lower(),
                                "passed": status == "PASSED",
                                "display_name": test_name.split("::")[-1]  # Just the function name
                            }
                        }
            
            process.wait()
            return_code = process.returncode
            
        except Exception as e:
            log(f"Error during streaming execution: {e}", "ERROR")
            yield {"event": "error", "data": {"error": str(e)}}
            return
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Get evidence report from conftest.py
        evidence_report = VerificationService.get_latest_evidence_report()
        
        # Collect evidence files from the latest session directory only
        # Find the most recent session directory
        session_dirs = sorted([d for d in evidence_dir.iterdir() if d.is_dir()], 
                            key=lambda d: d.stat().st_mtime, 
                            reverse=True)
        
        if session_dirs:
            latest_session = session_dirs[0]
            video_files = list(latest_session.glob("*.webm"))
            log(f"Found {len(video_files)} videos in latest session: {latest_session.name}")
        else:
            video_files = []
            log("No session directories found", "WARN")
        
        log_files = list(evidence_dir.glob("test_execution_*.log"))
        log_file = max(log_files, key=lambda f: f.stat().st_mtime) if log_files else None
        
        # Calculate final stats
        if evidence_report and evidence_report.get('tests', {}).get('details'):
            test_details = evidence_report['tests']['details']
            passed = evidence_report.get('tests', {}).get('passed', 0)
            failed = evidence_report.get('tests', {}).get('failed', 0)
            total = evidence_report.get('tests', {}).get('total', 0)
        else:
            test_details = []
            passed = len([t for t in tests_seen if 'PASSED' in str(t)])
            failed = len(tests_seen) - passed
            total = len(tests_seen)
        
        # Yield completion event
        yield {
            "event": "complete",
            "data": {
                "success": return_code == 0,
                "duration": duration,
                "passed": passed,
                "failed": failed,
                "total": total,
                "video_files": [str(v) for v in video_files],
                "log_file": str(log_file) if log_file else None,
                "evidence_dir": str(evidence_dir),
                "report_path": evidence_report.get('report_path', ''),
                "test_details": test_details
            }
        }
        
        log(f"Streaming execution complete: {passed}/{total} passed in {duration:.2f}s")
    
    @staticmethod
    def parse_pytest_output(stdout: str) -> List[Dict[str, Any]]:
        """
        Parse pytest verbose output to extract test results
        
        Args:
            stdout: Pytest stdout
            
        Returns:
            List of test results
        """
        test_results = []
        
        # Pattern to match pytest verbose output lines
        # e.g., "test_file.py::test_function PASSED" or "FAILED"
        pattern = r'(test_\w+\.py::test_\w+)\s+(PASSED|FAILED|SKIPPED|ERROR)'
        
        for match in re.finditer(pattern, stdout):
            test_name = match.group(1)
            status = match.group(2)
            test_results.append({
                "name": test_name,
                "status": status.lower(),
                "passed": status == "PASSED"
            })
        
        # Also extract failure details
        failure_pattern = r'FAILED (test_\w+\.py::test_\w+) - (.+?)(?=\n(?:FAILED|PASSED|=|$))'
        for match in re.finditer(failure_pattern, stdout, re.DOTALL):
            test_name = match.group(1)
            error_msg = match.group(2).strip()
            
            # Update the test result with error details
            for result in test_results:
                if result["name"] == test_name:
                    result["error"] = error_msg
                    break
        
        return test_results
    
    @staticmethod
    def run_single_test(test_file: str, test_name: str) -> Dict[str, Any]:
        """
        Run a single test function with video recording
        
        Args:
            test_file: Path to the test file
            test_name: Name of the specific test function
            
        Returns:
            Execution result
        """
        log(f"Running single test: {test_name}")
        
        evidence_dir = VerificationService.ensure_evidence_dir()
        VerificationService.generate_video_config()
        
        # Run specific test
        cmd = [
            "python", "-m", "pytest",
            f"{test_file}::{test_name}",
            "-v",
            "--tb=long"
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(BASE_DIR)
            )
            
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "test_name": test_name
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "test_name": test_name
            }
    
    @staticmethod
    def generate_refactor_prompt(
        code: str,
        test_results: Dict[str, Any],
        critique: str
    ) -> str:
        """
        Generate a prompt for refactoring based on test results and user critique
        
        Args:
            code: Current test code
            test_results: Results from test execution
            critique: User's critique/feedback
            
        Returns:
            Refactoring prompt
        """
        failed_tests = [t for t in test_results.get('test_results', []) if not t.get('passed', True)]
        
        failure_details = ""
        if failed_tests:
            failure_details = "FAILED TESTS:\n"
            for ft in failed_tests:
                failure_details += f"  - {ft['name']}: {ft.get('error', 'Unknown error')}\n"
        
        return f'''The following Playwright test code needs to be refactored based on execution results and user feedback.

CURRENT CODE:
```python
{code}
```

TEST EXECUTION RESULTS:
- Success: {test_results.get('success', False)}
- Return Code: {test_results.get('return_code', -1)}
- Duration: {test_results.get('duration', 0):.2f}s
- Tests Passed: {len([t for t in test_results.get('test_results', []) if t.get('passed')])}
- Tests Failed: {len(failed_tests)}

{failure_details}

STDOUT:
{test_results.get('stdout', '')[:2000]}

STDERR:
{test_results.get('stderr', '')[:1000]}

USER CRITIQUE:
{critique}

CRITICAL PLAYWRIGHT API RULES - MUST FOLLOW:
- get_by_text() does NOT have ignore_case parameter - just use page.get_by_text("text")
- get_by_role() valid params: name, exact, checked, disabled, expanded, pressed, selected, level
- When multiple elements match, use .first, .last, or .nth(n) to avoid strict mode errors
- Use relative URLs in href selectors: a[href='/products'] NOT a[href='https://site.com/products']
- For flexible counts, use greater_than/less_than: expect(locator).to_have_count(count) or check dynamically

Please refactor the code to:
1. Fix any failing tests - especially API usage errors like invalid parameters
2. Address the user's critique
3. Handle strict mode violations by using .first when multiple elements match
4. Use relative href selectors instead of absolute URLs
5. Add proper waits and error handling
6. Make count assertions flexible or verify actual counts first

Return ONLY the complete, corrected Python code - no markdown, no explanations.
Start with the imports and end with the last line of code.'''

    @staticmethod
    def refactor_tests(
        code: str,
        test_results: Dict[str, Any],
        critique: str,
        page_structure: Dict[str, Any],
        llm_call: Callable
    ) -> Dict[str, Any]:
        """
        Refactor test code based on execution results and user critique
        
        Args:
            code: Current test code
            test_results: Results from test execution
            critique: User's feedback/critique
            page_structure: Page structure for context
            llm_call: LLM call function
            
        Returns:
            Refactoring result with new code
        """
        log("========== REFACTORING TESTS ==========")
        log(f"User critique: {critique[:100]}...")
        
        prompt = VerificationService.generate_refactor_prompt(code, test_results, critique)
        
        result = llm_call(prompt)
        
        # Clean the response
        new_code = result['text'].strip()
        new_code = re.sub(r'```python|```', '', new_code).strip()
        
        # Remove any non-code content
        lines = new_code.split('\n')
        valid_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('**') or stripped.startswith('##'):
                break
            valid_lines.append(line)
        new_code = '\n'.join(valid_lines).strip()
        
        log(f"Refactored code: {len(new_code)} characters")
        
        return {
            'code': new_code,
            'response_time': result['response_time'],
            'tokens_used': result['tokens_used']
        }
    
    @staticmethod
    def save_refactored_code(code: str, original_path: str) -> str:
        """
        Save refactored code to a new file
        
        Args:
            code: Refactored code
            original_path: Original test file path
            
        Returns:
            Path to the new file
        """
        from services.implementation_service import ImplementationService
        
        # Create a new filename with refactored suffix
        original = Path(original_path)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        new_filename = f"{original.stem}_refactored_{timestamp}.py"
        new_path = original.parent / new_filename
        
        # Add header
        header = f'''"""
Refactored Playwright Test
Original: {original.name}
Refactored on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

To run this test:
    pytest {new_filename} --headed
"""

'''
        
        with open(new_path, 'w', encoding='utf-8') as f:
            f.write(header + code)
        
        log(f"Refactored code saved to: {new_path}")
        return str(new_path)
    
    @staticmethod
    def get_latest_evidence_report() -> Dict[str, Any]:
        """
        Get the most recent evidence report generated by conftest.py
        
        Returns:
            Evidence report dict or empty dict if not found
        """
        report_files = list(EVIDENCE_DIR.glob("report_*.json"))
        if not report_files:
            return {}
        
        latest_report = max(report_files, key=lambda f: f.stat().st_mtime)
        try:
            with open(latest_report, 'r', encoding='utf-8') as f:
                report = json.load(f)
            report["report_path"] = str(latest_report)
            return report
        except Exception as e:
            log(f"Error reading evidence report: {e}", "ERROR")
            return {}
    
    @staticmethod
    def verify(
        code: str,
        test_cases: List[Dict[str, Any]],
        llm_call: Callable,
        test_file_path: Optional[str] = None,
        headed: bool = False
    ) -> Dict[str, Any]:
        """
        Verify test code by actually running it and collecting evidence
        
        Args:
            code: Generated test code
            test_cases: Test cases
            llm_call: LLM call function
            test_file_path: Path to the test file (optional)
            
        Returns:
            Verification result with execution details and evidence
        """
        log("========== STARTING REAL VERIFICATION ==========")
        
        # Find the test file
        if not test_file_path:
            # Find the most recent test file
            test_files = sorted(TESTS_DIR.glob("test_*.py"), key=os.path.getmtime, reverse=True)
            if test_files:
                test_file_path = str(test_files[0])
                log(f"Using most recent test file: {test_file_path}")
            else:
                log("No test files found!", "ERROR")
                return {
                    "report": {
                        "status": "error",
                        "summary": "No test files found to execute",
                        "tests": [],
                        "issues": ["No test files found in tests directory"],
                        "recommendations": ["Generate test code first using the implement phase"]
                    },
                    "response_time": 0,
                    "tokens_used": 0
                }
        
        # Run the tests with video recording
        log(f"Executing tests from: {test_file_path}")
        log(f"Headed mode: {headed}")
        execution_result = VerificationService.run_pytest_with_video(test_file_path, headed=headed)
        
        # Get evidence report generated by conftest.py
        evidence_report = VerificationService.get_latest_evidence_report()
        
        # Build the verification report - use evidence_report if available, fallback to execution_result
        if evidence_report:
            passed_count = evidence_report.get('tests', {}).get('passed', 0)
            failed_count = evidence_report.get('tests', {}).get('failed', 0)
            total_count = evidence_report.get('tests', {}).get('total', 0)
        else:
            # Fallback to parsing from execution_result
            test_results = execution_result.get('test_results', [])
            passed_count = len([t for t in test_results if t.get('passed')])
            failed_count = len([t for t in test_results if not t.get('passed')])
            total_count = len(test_results)
        
        status = "passed" if execution_result['success'] else "failed"
        
        # Use evidence_report test details if available, otherwise fall back to parsed results
        if evidence_report and evidence_report.get('tests', {}).get('details'):
            test_details = evidence_report['tests']['details']
        else:
            test_details = execution_result.get('test_results', [])
        
        report = {
            "status": status,
            "summary": f"Executed {total_count} tests: {passed_count} passed, {failed_count} failed",
            "tests": [
                {
                    "name": t.get('name', 'unknown'),
                    "status": t.get('status', 'unknown'),
                    "duration": t.get('duration', 'N/A'),
                    "error": t.get('error', None)
                }
                for t in test_details
            ],
            "issues": [
                t.get('error', f"{t.get('name', 'unknown')} failed") 
                for t in test_details
                if not t.get('passed')
            ],
            "recommendations": [],
            "evidence": {
                "video_files": execution_result.get('video_files', []),
                "evidence_dir": str(EVIDENCE_DIR),
                "report_path": evidence_report.get('report_path', '')
            },
            "execution_details": {
                "duration": execution_result.get('duration', 0),
                "return_code": execution_result.get('return_code', -1),
                "stdout_preview": execution_result.get('stdout', '')[:500]
            }
        }
        
        # Add recommendations based on results
        if failed_count > 0:
            report["recommendations"].append("Review failed tests and use the critique feature to refactor")
            report["recommendations"].append("Check element locators - they may have changed")
            report["recommendations"].append("Add explicit waits for dynamic elements")
        
        if execution_result.get('video_files'):
            report["recommendations"].append(f"Review video evidence at: {EVIDENCE_DIR}")
        
        log(f"========== VERIFICATION COMPLETE ==========")
        log(f"Status: {status}")
        log(f"Tests: {passed_count}/{total_count} passed")
        log(f"Videos: {len(execution_result.get('video_files', []))} captured")
        
        return {
            'report': report,
            'execution_result': execution_result,
            'evidence_report': evidence_report,
            'test_file': test_file_path,
            'response_time': execution_result.get('duration', 0),
            'tokens_used': 0  # No LLM tokens used for execution
        }
    
    @staticmethod
    def handle_critique(
        critique: str,
        code: str,
        test_results: Dict[str, Any],
        page_structure: Dict[str, Any],
        llm_call: Callable
    ) -> Dict[str, Any]:
        """
        Handle user critique and refactor tests accordingly
        
        Args:
            critique: User's critique/feedback
            code: Current test code
            test_results: Results from verification
            page_structure: Page structure for context
            llm_call: LLM call function
            
        Returns:
            Result with refactored code and new file path
        """
        log("========== HANDLING USER CRITIQUE ==========")
        log(f"Critique: {critique}")
        
        # Refactor based on critique
        refactor_result = VerificationService.refactor_tests(
            code=code,
            test_results=test_results,
            critique=critique,
            page_structure=page_structure,
            llm_call=llm_call
        )
        
        # Save the refactored code
        original_path = test_results.get('test_file', str(TESTS_DIR / 'test_refactored.py'))
        new_path = VerificationService.save_refactored_code(
            refactor_result['code'],
            original_path
        )
        
        # Re-run tests on the refactored code
        log("Re-running tests on refactored code...")
        new_execution = VerificationService.run_pytest_with_video(new_path)
        new_evidence = VerificationService.get_latest_evidence_report()
        
        return {
            'refactored_code': refactor_result['code'],
            'new_file_path': new_path,
            'execution_result': new_execution,
            'evidence_report': new_evidence,
            'response_time': refactor_result['response_time'],
            'tokens_used': refactor_result['tokens_used'],
            'improvement': {
                'original_passed': len([t for t in test_results.get('execution_result', {}).get('test_results', []) if t.get('passed')]),
                'new_passed': len([t for t in new_execution.get('test_results', []) if t.get('passed')])
            }
        }


# Singleton instance
verification_service = VerificationService()
