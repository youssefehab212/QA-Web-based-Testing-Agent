"""
Implementation Service
Handles test code generation and file creation

IMPLEMENTATION STRATEGY:
1. Locator Strategy: Priority-based locator selection (ID > data-testid > aria > name > text > CSS > XPath)
2. Self-Correction: Syntax validation with AST + iterative LLM refinement
"""

import json
import re
import os
import ast
from datetime import datetime
from typing import Dict, Any, List, Callable, Tuple


def log(message: str, level: str = "INFO"):
    """Print a formatted log message with timestamp"""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] [{level}] [Implementation] {message}")


class ImplementationService:
    """Service for implementing test code with smart locator strategy and self-correction"""
    
    # Base directory for tests
    TESTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'tests')
    
    # Maximum self-correction attempts
    MAX_CORRECTION_ATTEMPTS = 3
    
    # Locator strategy documentation for the LLM
    LOCATOR_STRATEGY = """
LOCATOR PRIORITY (use in order):
1. ID: `page.locator("#login-btn")`
2. data-testid: `page.get_by_test_id("submit")`
3. role + name: `page.get_by_role("button", name="Submit")`
4. placeholder: `page.get_by_placeholder("Enter email")`
5. text: `page.get_by_text("Login")`
6. CSS: `page.locator(".btn-primary")`

CRITICAL RULES:
- ALWAYS use .first when multiple matches possible: `page.get_by_role("link", name="Home").first`
- ALWAYS use wait_until="domcontentloaded": `page.goto(url, wait_until="domcontentloaded")`
- NEVER use wait_for_load_state("networkidle") - causes timeouts
- After navigation clicks, use: `page.wait_for_url("**/path**")`
- For new tabs: `new_page.wait_for_load_state("domcontentloaded")`
- get_by_text() has NO ignore_case param - use `page.locator("text=/pattern/i")` for case-insensitive

TIMING (wait before asserting):
- After clicking expandable elements: `content.wait_for(state="visible", timeout=5000)`
- For footer elements: `element.scroll_into_view_if_needed()`
- After form submit: `success_msg.wait_for(state="visible", timeout=5000)`
- NEVER assert immediately after clicking

FORM VALIDATION:
- HTML5 validation uses browser tooltips, not DOM elements
- Test with: `is_invalid = input.evaluate("el => !el.validity.valid")`
- Only look for custom error messages if site uses JS validation

SPECIAL CASES:
- mailto: links open email client, not browser navigation - don't use expect_navigation
- Menu links usually navigate same window - don't use expect_page() unless target="_blank"
- Form fields may NOT clear after submission - assert success message visibility instead
"""

    @staticmethod
    def generate_prompt(test_cases: List[Dict[str, Any]], page_structure: Dict[str, Any]) -> str:
        """
        Generate the implementation prompt with locator strategy guidance
        
        Args:
            test_cases: Test cases to implement
            page_structure: Page structure
            
        Returns:
            The implementation prompt
        """
        log("Generating implementation prompt with locator strategy...")
        
        # Extract element locator info if available
        elements_info = ""
        elements = page_structure.get('elements', [])
        if elements:
            log(f"Including {min(len(elements), 20)} element locators in prompt")
            elements_info = f"""
AVAILABLE ELEMENTS WITH LOCATORS:
{json.dumps(elements[:20], indent=2)}

Use the locator information above to select the best locator for each element.
"""

        return f'''Generate Python + Playwright test code for these test cases:
{json.dumps(test_cases, indent=2)}

Page structure:
{json.dumps({k: v for k, v in page_structure.items() if k != 'elements'}, indent=2)}

{elements_info}

{ImplementationService.LOCATOR_STRATEGY}

OUTPUT REQUIREMENTS:
- Return ONLY valid Python code - no markdown, no ```python blocks, no explanations
- Code will be validated with AST parser - must be syntactically correct
- Do NOT define @pytest.fixture - fixtures are provided by conftest.py
- Test functions accept `page` parameter: `def test_example(page):`

COMMON MISTAKES:
- NEVER use networkidle - causes timeouts
- NEVER assert immediately after clicking - wait first
- NEVER use expect_page() unless link has target="_blank"
- NEVER use expect_navigation() on mailto: links
- ALWAYS use .first for elements that may match multiple times
- ALWAYS scroll_into_view_if_needed() for footer elements
- ALWAYS wait_for(state="visible") after clicking expandable elements
- Form fields may NOT clear after submit - assert success message visibility instead
- Use validity API for HTML5 validation, not custom error messages

ASSERTIONS (every test MUST have at least one):
- URL: `assert "/path" in page.url` (use `in`, not `==`)
- Visibility: `element.wait_for(state="visible"); assert element.is_visible()`
- Text: `assert "text" in element.text_content()`
- Count: `assert locator.count() > 0`
- Form validity: `assert input.evaluate("el => !el.validity.valid")`

Start directly with imports, end with last line of code.'''

    @staticmethod
    def parse_response(response_text: str, page_structure: Dict[str, Any], test_cases: List[Dict[str, Any]]) -> str:
        """
        Parse and clean the implementation response
        
        Args:
            response_text: Raw response from LLM
            page_structure: Page structure
            test_cases: Test cases
            
        Returns:
            Cleaned code
        """
        # Remove markdown code blocks if present
        code = re.sub(r'```python|```', '', response_text).strip()
        
        # Remove any "How to run" or similar sections at the end
        # Look for common patterns that indicate non-code content
        patterns_to_remove = [
            r'\n\s*\*\*How to run\*\*.*',  # **How to run** sections
            r'\n\s*## How to.*',            # ## How to headers
            r'\n\s*# How to run.*',         # # How to run comments at end
            r'\n\s*---\s*\n.*',             # Horizontal rules and content after
            r'\n\s*\*\*Note:?\*\*.*',       # **Note:** sections
            r'\n\s*bash\s*\n.*pip install.*',  # bash install commands
            r'\n\s*```bash.*?```',          # bash code blocks
            r'\n\s*```\s*\n.*?```',         # any remaining code blocks
        ]
        
        for pattern in patterns_to_remove:
            code = re.sub(pattern, '', code, flags=re.DOTALL | re.IGNORECASE)
        
        # Remove any fixture definitions - these override conftest.py and break video recording
        # Pattern matches @pytest.fixture decorator and the function that follows
        fixture_pattern = r'@pytest\.fixture[^\n]*\ndef\s+\w+\([^)]*\):[^@]*?(?=\n(?:@|def\s+test_|\Z))'
        code = re.sub(fixture_pattern, '', code, flags=re.DOTALL)
        
        # Also remove standalone browser/page fixture patterns
        browser_fixture = r'@pytest\.fixture\(scope="session"\)\s*\ndef browser\(\):[^@]*?(?=\n(?:@|def\s+test_|\Z))'
        page_fixture = r'@pytest\.fixture[^\n]*\s*\ndef page\([^)]*\):[^@]*?(?=\n(?:@|def\s+test_|\Z))'
        code = re.sub(browser_fixture, '', code, flags=re.DOTALL)
        code = re.sub(page_fixture, '', code, flags=re.DOTALL)
        
        # Clean up multiple blank lines left after removing fixtures
        code = re.sub(r'\n{3,}', '\n\n', code)
        
        # Find where the actual Python code ends (last valid Python line)
        lines = code.split('\n')
        valid_lines = []
        for line in lines:
            stripped = line.strip()
            # Stop if we hit non-Python content
            if stripped.startswith('**') or stripped.startswith('##') or stripped.startswith('bash'):
                break
            valid_lines.append(line)
        
        code = '\n'.join(valid_lines).strip()
        
        # If code doesn't have imports, add basic structure
        if 'import' not in code:
            code = ImplementationService.get_default_code(page_structure, test_cases)
        
        return code
    
    @staticmethod
    def get_default_code(page_structure: Dict[str, Any], test_cases: List[Dict[str, Any]]) -> str:
        """
        Get default code template
        
        Args:
            page_structure: Page structure
            test_cases: Test cases
            
        Returns:
            Default code
        """
        url = page_structure.get('url', 'https://example.com')
        test_comments = '\n    '.join([f"# {tc.get('title', 'Test')}" for tc in test_cases])
        
        return f'''from playwright.sync_api import Page, expect

def test_example(page: Page):
    """Generated test based on test cases"""
    page.goto("{url}")
    
    {test_comments}
'''

    # ==================== SELF-CORRECTION METHODS ====================
    
    @staticmethod
    def validate_syntax(code: str) -> Tuple[bool, List[str]]:
        """
        Validate Python syntax using AST parser
        
        Args:
            code: Python code to validate
            
        Returns:
            Tuple of (is_valid, list of errors)
        """
        log("Validating Python syntax with AST parser...")
        errors = []
        
        try:
            ast.parse(code)
            log("✓ Syntax validation passed")
            return True, []
        except SyntaxError as e:
            error_msg = f"Line {e.lineno}: {e.msg}"
            if e.text:
                error_msg += f" -> '{e.text.strip()}'"
            log(f"✗ Syntax error: {error_msg}", "ERROR")
            errors.append(error_msg)
            return False, errors
        except Exception as e:
            error_msg = f"Parse error: {str(e)}"
            log(f"✗ {error_msg}", "ERROR")
            errors.append(error_msg)
            return False, errors
    
    @staticmethod
    def validate_structure(code: str) -> Tuple[bool, List[str]]:
        """
        Validate code structure (imports, test functions, etc.)
        
        Args:
            code: Python code to validate
            
        Returns:
            Tuple of (is_valid, list of issues)
        """
        log("Validating code structure...")
        issues = []
        
        # Check for Playwright imports
        if 'playwright' not in code.lower():
            issues.append("Missing Playwright import")
            log("✗ Missing Playwright import", "WARN")
        
        # Check for test functions
        test_funcs = re.findall(r'def (test_\w+)\s*\(', code)
        if not test_funcs:
            issues.append("No test functions found (expected 'def test_*')")
            log("✗ No test functions found", "WARN")
        else:
            log(f"✓ Found {len(test_funcs)} test function(s): {', '.join(test_funcs)}")
        
        # Check for page.goto
        if 'page.goto' not in code and '.goto(' not in code:
            issues.append("No page.goto() call - tests should navigate to target URL")
            log("⚠ No page.goto() found", "WARN")
        
        # Check for assertions
        if 'expect(' not in code and 'assert ' not in code:
            issues.append("No assertions found - tests should verify outcomes")
            log("⚠ No assertions found", "WARN")
        
        # Check for semantic locators (recommended)
        semantic_locators = ['get_by_role', 'get_by_text', 'get_by_label', 'get_by_placeholder', 'get_by_test_id']
        has_semantic = any(loc in code for loc in semantic_locators)
        if has_semantic:
            log("✓ Uses semantic Playwright locators (recommended)")
        else:
            log("⚠ Consider using semantic locators for better stability", "WARN")
        
        return len([i for i in issues if 'No test functions' in i or 'Missing Playwright' in i]) == 0, issues
    
    @staticmethod
    def generate_correction_prompt(code: str, errors: List[str]) -> str:
        """
        Generate a prompt to fix code issues
        
        Args:
            code: The problematic code
            errors: List of errors/issues to fix
            
        Returns:
            Correction prompt
        """
        return f'''The following Playwright test code has issues that need to be fixed:

ISSUES FOUND:
{chr(10).join(f"- {error}" for error in errors)}

ORIGINAL CODE:
{code}

Please fix ALL the issues and return the corrected Python code.

REQUIREMENTS:
1. Return ONLY pure Python code - no markdown, no explanations
2. Do NOT include ```python or ``` markers
3. Fix all syntax errors
4. Ensure all required imports are present (from playwright.sync_api import Page, expect)
5. Ensure test functions follow pytest conventions (def test_*)
6. Include page.goto() to navigate to the target URL
7. Include at least one assertion using expect()

{ImplementationService.LOCATOR_STRATEGY}

Return the complete, corrected Python code:'''

    @staticmethod
    def implement_with_self_correction(
        test_cases: List[Dict[str, Any]], 
        page_structure: Dict[str, Any], 
        llm_call: Callable
    ) -> Dict[str, Any]:
        """
        Implement test code with self-correction loop
        
        This method:
        1. Generates initial code
        2. Validates syntax and structure
        3. If issues found, asks LLM to fix
        4. Repeats up to MAX_CORRECTION_ATTEMPTS times
        
        Args:
            test_cases: Test cases to implement
            page_structure: Page structure
            llm_call: LLM call function
            
        Returns:
            Implementation result with code, corrections info, and metrics
        """
        log("========== IMPLEMENTATION WITH SELF-CORRECTION ==========")
        log(f"Test cases to implement: {len(test_cases)}")
        log(f"Max correction attempts: {ImplementationService.MAX_CORRECTION_ATTEMPTS}")
        
        total_response_time = 0
        total_tokens = 0
        correction_history = []
        
        # Step 1: Generate initial code
        log("--- Step 1: Initial Code Generation ---")
        prompt = ImplementationService.generate_prompt(test_cases, page_structure)
        result = llm_call(prompt)
        total_response_time += result.get('response_time', 0)
        total_tokens += result.get('tokens_used', 0)
        
        current_code = ImplementationService.parse_response(result['text'], page_structure, test_cases)
        log(f"Initial code generated: {len(current_code)} characters")
        
        # Step 2: Self-correction loop
        for attempt in range(ImplementationService.MAX_CORRECTION_ATTEMPTS):
            log(f"--- Correction Attempt {attempt + 1}/{ImplementationService.MAX_CORRECTION_ATTEMPTS} ---")
            
            # Validate syntax
            syntax_ok, syntax_errors = ImplementationService.validate_syntax(current_code)
            
            # Validate structure
            structure_ok, structure_issues = ImplementationService.validate_structure(current_code)
            
            all_issues = syntax_errors + [i for i in structure_issues if 'Missing' in i or 'No test' in i]
            
            if syntax_ok and not all_issues:
                log(f"✓ Code passed all validations on attempt {attempt + 1}")
                break
            
            # Code has issues - request correction
            log(f"Found {len(all_issues)} critical issues - requesting LLM correction...")
            correction_history.append({
                'attempt': attempt + 1,
                'issues': all_issues
            })
            
            correction_prompt = ImplementationService.generate_correction_prompt(current_code, all_issues)
            
            try:
                correction_result = llm_call(correction_prompt)
                total_response_time += correction_result.get('response_time', 0)
                total_tokens += correction_result.get('tokens_used', 0)
                
                corrected_code = ImplementationService.parse_response(
                    correction_result['text'], 
                    page_structure, 
                    test_cases
                )
                
                if corrected_code and corrected_code != current_code:
                    log(f"Received corrected code ({len(corrected_code)} characters)")
                    current_code = corrected_code
                else:
                    log("LLM returned same or empty code, stopping correction loop", "WARN")
                    break
                    
            except Exception as e:
                log(f"Correction attempt failed: {e}", "ERROR")
                break
        
        # Final validation
        final_syntax_ok, _ = ImplementationService.validate_syntax(current_code)
        final_structure_ok, final_issues = ImplementationService.validate_structure(current_code)
        
        # Save the code
        file_path = ImplementationService.save_test_file(current_code, page_structure)
        
        log("========== IMPLEMENTATION COMPLETE ==========")
        log(f"Final code: {len(current_code)} characters")
        log(f"Correction attempts: {len(correction_history)}")
        log(f"Syntax valid: {final_syntax_ok}")
        log(f"Saved to: {file_path}")
        
        return {
            'code': current_code,
            'file_path': file_path,
            'response_time': total_response_time,
            'tokens_used': total_tokens,
            'self_correction': {
                'attempts': len(correction_history),
                'history': correction_history,
                'final_syntax_valid': final_syntax_ok,
                'final_structure_valid': final_structure_ok,
                'final_issues': final_issues
            }
        }

    @staticmethod
    def implement(test_cases: List[Dict[str, Any]], page_structure: Dict[str, Any], llm_call: Callable) -> Dict[str, Any]:
        """
        Implement test code based on test cases (with self-correction)
        
        Args:
            test_cases: Test cases to implement
            page_structure: Page structure
            llm_call: LLM call function
            
        Returns:
            Implementation result with code, response_time, tokens_used, and file_path
        """
        # Use the self-correction implementation
        return ImplementationService.implement_with_self_correction(test_cases, page_structure, llm_call)
    
    @staticmethod
    def ensure_tests_directory() -> str:
        """
        Ensure the tests directory exists
        
        Returns:
            Path to the tests directory
        """
        if not os.path.exists(ImplementationService.TESTS_DIR):
            os.makedirs(ImplementationService.TESTS_DIR)
        
        # Create __init__.py if it doesn't exist
        init_file = os.path.join(ImplementationService.TESTS_DIR, '__init__.py')
        if not os.path.exists(init_file):
            with open(init_file, 'w') as f:
                f.write('# Auto-generated test package\n')
        
        return ImplementationService.TESTS_DIR
    
    @staticmethod
    def generate_test_filename(page_structure: Dict[str, Any]) -> str:
        """
        Generate a unique filename for the test file
        
        Args:
            page_structure: Page structure containing URL info
            
        Returns:
            Generated filename
        """
        # Extract domain from URL for naming
        url = page_structure.get('url', 'unknown')
        
        # Clean the URL to create a valid filename
        # Remove protocol and special characters
        clean_name = re.sub(r'https?://', '', url)
        clean_name = re.sub(r'[^\w\-]', '_', clean_name)
        clean_name = clean_name[:30]  # Limit length
        
        # Add timestamp for uniqueness
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        return f"test_{clean_name}_{timestamp}.py"
    
    @staticmethod
    def save_test_file(code: str, page_structure: Dict[str, Any]) -> str:
        """
        Save the generated test code to a file
        
        Args:
            code: The generated test code
            page_structure: Page structure for naming
            
        Returns:
            Full path to the saved file
        """
        # Ensure tests directory exists
        tests_dir = ImplementationService.ensure_tests_directory()
        
        # Generate filename
        filename = ImplementationService.generate_test_filename(page_structure)
        file_path = os.path.join(tests_dir, filename)
        
        # Add file header with metadata
        header = f'''"""
Auto-generated Playwright Test
Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Target URL: {page_structure.get('url', 'N/A')}
Page Type: {page_structure.get('pageMetadata', {}).get('type', 'N/A')}

To run this test:
    pytest {filename}
    
Or with Playwright:
    python -m pytest {filename} --headed
"""

'''
        
        # Write the file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(header + code)
        
        print(f"Test file saved: {file_path}")
        
        return file_path
    
    @staticmethod
    def read_test_file(file_path: str) -> str:
        """
        Read a test file
        
        Args:
            file_path: Path to the test file
            
        Returns:
            Content of the test file
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    @staticmethod
    def list_test_files() -> List[Dict[str, Any]]:
        """
        List all test files in the tests directory
        
        Returns:
            List of test file info (name, path, modified time)
        """
        tests_dir = ImplementationService.TESTS_DIR
        
        if not os.path.exists(tests_dir):
            return []
        
        test_files = []
        for filename in os.listdir(tests_dir):
            if filename.startswith('test_') and filename.endswith('.py'):
                file_path = os.path.join(tests_dir, filename)
                test_files.append({
                    'name': filename,
                    'path': file_path,
                    'modified': datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()
                })
        
        return sorted(test_files, key=lambda x: x['modified'], reverse=True)


# Singleton instance
implementation_service = ImplementationService()
