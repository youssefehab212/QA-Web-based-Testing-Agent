"""
Design Service
Handles test case design and generation
"""

import json
import os
import re
from datetime import datetime
from typing import Dict, Any, List, Callable
from urllib.parse import urlparse

# Output directory for JSON files
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'output')


def log(message: str, level: str = "INFO"):
    """Print a formatted log message with timestamp"""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] [{level}] [Design] {message}")


def ensure_output_dir():
    """Ensure the output directory exists"""
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        log(f"Created output directory: {OUTPUT_DIR}")
    return OUTPUT_DIR


def get_domain_from_url(url: str) -> str:
    """Extract domain name from URL for file naming"""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.replace('www.', '').replace('.', '_')
        return domain[:30]  # Limit length
    except:
        return "unknown"


class DesignService:
    """Service for designing test cases"""
    
    @staticmethod
    def save_test_cases(test_cases: List[Dict[str, Any]], page_structure: Dict[str, Any]) -> str:
        """
        Save the test cases to a JSON file
        
        Args:
            test_cases: The generated test cases
            page_structure: The page structure (for URL info)
            
        Returns:
            Path to the saved file
        """
        ensure_output_dir()
        
        url = page_structure.get('url', 'unknown')
        domain = get_domain_from_url(url)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"test_cases_{domain}_{timestamp}.json"
        filepath = os.path.join(OUTPUT_DIR, filename)
        
        # Create a comprehensive test cases file
        test_data = {
            "metadata": {
                "url": url,
                "timestamp": datetime.now().isoformat(),
                "total_test_cases": len(test_cases),
                "page_title": page_structure.get('pageMetadata', {}).get('title', 'Unknown'),
                "page_type": page_structure.get('pageMetadata', {}).get('type', 'generic')
            },
            "test_cases": test_cases,
            "summary": {
                "high_priority": len([tc for tc in test_cases if tc.get('priority') == 'high']),
                "medium_priority": len([tc for tc in test_cases if tc.get('priority') == 'medium']),
                "low_priority": len([tc for tc in test_cases if tc.get('priority') == 'low']),
                "functional": len([tc for tc in test_cases if tc.get('type') == 'functional']),
                "ui": len([tc for tc in test_cases if tc.get('type') == 'ui']),
                "integration": len([tc for tc in test_cases if tc.get('type') == 'integration'])
            }
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(test_data, f, indent=2, ensure_ascii=False)
        
        log(f"Test cases saved to: {filepath}")
        return filepath
    
    @staticmethod
    def generate_prompt(page_structure: Dict[str, Any], user_input: str = "") -> str:
        """
        Generate the design prompt for test cases
        
        Args:
            page_structure: The page structure from exploration
            user_input: Optional user input to guide test case generation
            
        Returns:
            The design prompt
        """
        log("Generating test case design prompt...")
        log(f"  - URL: {page_structure.get('url', 'N/A')}")
        log(f"  - Elements available: {len(page_structure.get('elements', []))}")
        log(f"  - User flows available: {len(page_structure.get('userFlows', []))}")
        log(f"  - User input: {user_input if user_input else 'None'}")
        
        user_guidance = ""
        if user_input:
            user_guidance = f"""\nUSER GUIDANCE:
The user has provided the following input to guide test case generation:
"{user_input}"

Please take this guidance into account when designing the test cases.
"""
        
        return f'''Based on this page structure:
{json.dumps(page_structure, indent=2)}
{user_guidance}

Generate a COMPREHENSIVE test plan that includes coverage of:

1. Navigation behavior
2. Valid input scenarios
3. Invalid input scenarios
4. Boundary cases
5. Post-condition behavior
6. UI responsiveness

DO NOT test any element or feature NOT present in the provided page structure.
DO NOT expect any field names or keywords without prior knowledge of the provided page structure.

Return ONLY a JSON array of test cases:
[
  {{
    "id": "TC001",
    "title": "Test case title",
    "priority": "high|medium|low",
    "type": "functional|ui|integration",
    "steps": ["Step 1", "Step 2", "Step 3"],
    "expectedResult": "Expected outcome",
    "elements": ["#selector1", "#selector2"]
  }}
]

'''

    @staticmethod
    def parse_response(response_text: str) -> List[Dict[str, Any]]:
        """
        Parse the design response
        
        Args:
            response_text: Raw response from LLM
            
        Returns:
            Parsed test cases
        """
        log("========== PARSING LLM RESPONSE ==========")
        log(f"Raw response length: {len(response_text)} characters")
        
        try:
            # Remove markdown code blocks if present
            log("Cleaning response (removing markdown code blocks)...")
            clean_text = re.sub(r'```json|```', '', response_text).strip()
            
            log("Attempting to parse as JSON...")
            parsed = json.loads(clean_text)
            log(f"JSON parsed successfully!")
            log(f"Test cases parsed: {len(parsed)}")
            return parsed
        except json.JSONDecodeError as e:
            log(f"JSON parse error: {e}", "ERROR")
            log("Returning default test cases", "WARN")
            return DesignService.get_default_test_cases()
        except Exception as e:
            log(f"Unexpected error during parsing: {e}", "ERROR")
            return DesignService.get_default_test_cases()
    
    @staticmethod
    def get_default_test_cases() -> List[Dict[str, Any]]:
        """
        Get default test cases when parsing fails
        
        Returns:
            Default test cases
        """
        log("Creating default test cases (parsing failed)", "WARN")
        return [
            {
                "id": "TC001",
                "title": "Verify successful login with valid credentials",
                "priority": "high",
                "type": "functional",
                "steps": ["Navigate to page", "Enter valid username", "Enter valid password", "Click login button"],
                "expectedResult": "User is logged in successfully",
                "elements": ["#username", "#password", "#login-btn"]
            }
        ]
    
    @staticmethod
    def design(page_structure: Dict[str, Any], llm_call: Callable, user_input: str = "") -> Dict[str, Any]:
        """
        Design test cases based on page structure
        
        Args:
            page_structure: Page structure from exploration
            llm_call: LLM call function
            user_input: Optional user input to guide test case generation
            
        Returns:
            Design result with test_cases, response_time, and tokens_used
        """
        log("=" * 60)
        log("========== STARTING DESIGN PHASE ==========")
        log("=" * 60)
        
        # Step 1: Generate prompt
        log("")
        log(">>> STEP 1: GENERATING PROMPT <<<")
        prompt = DesignService.generate_prompt(page_structure, user_input)
        log(f"Prompt generated: {len(prompt)} characters")
        
        # Step 2: Call LLM
        log("")
        log(">>> STEP 2: CALLING LLM <<<")
        log("Sending prompt...")
        result = llm_call(prompt)
        log(f"LLM response received!")
        log(f"  - Response time: {result.get('response_time', 0):.2f}s")
        log(f"  - Tokens used: {result.get('tokens_used', 0)}")
        
        # Step 3: Parse response
        log("")
        log(">>> STEP 3: PARSING RESPONSE <<<")
        test_cases = DesignService.parse_response(result['text'])
        
        # Step 4: Save test cases to JSON
        log("")
        log(">>> STEP 4: SAVING TEST CASES <<<")
        test_cases_path = DesignService.save_test_cases(test_cases, page_structure)
        
        # Final summary
        log("")
        log(">>> DESIGN COMPLETE <<<")
        log(f"  - Total test cases: {len(test_cases)}")
        log(f"  - High priority: {len([tc for tc in test_cases if tc.get('priority') == 'high'])}")
        log(f"  - Medium priority: {len([tc for tc in test_cases if tc.get('priority') == 'medium'])}")
        log(f"  - Low priority: {len([tc for tc in test_cases if tc.get('priority') == 'low'])}")
        log(f"  - Test cases saved to: {test_cases_path}")
        log("=" * 60)
        
        return {
            'test_cases': test_cases,
            'test_cases_path': test_cases_path,
            'response_time': result['response_time'],
            'tokens_used': result['tokens_used']
        }

    @staticmethod
    def refine_test_cases(
        user_feedback: str,
        current_test_cases: List[Dict[str, Any]],
        page_structure: Dict[str, Any],
        llm_call: Callable
    ) -> Dict[str, Any]:
        """
        Refine test cases based on user feedback (add, modify, remove)
        
        Args:
            user_feedback: The user's refinement request
            current_test_cases: Existing test cases
            page_structure: The page structure from exploration
            llm_call: LLM call function
            
        Returns:
            Result with updated test_cases and a message
        """
        log("=" * 60)
        log("========== REFINING TEST CASES ==========")
        log(f"User feedback: {user_feedback}")
        log(f"Current test cases: {len(current_test_cases)}")
        log("=" * 60)
        
        # Build a context-aware prompt for refinement
        elements_summary = []
        for el in page_structure.get('elements', [])[:15]:
            el_text = (el.get('text') or el.get('name') or el.get('type') or '')[:30]
            elements_summary.append(f"- {el.get('type', 'element')}: {el_text}")
        
        forms_summary = []
        for form in page_structure.get('forms', [])[:5]:
            form_fields = [f.get('name', 'field') for f in form.get('inputs', [])[:5]]
            forms_summary.append(f"- Form: {', '.join(form_fields)}")
        
        current_tc_summary = []
        for i, tc in enumerate(current_test_cases, 1):
            current_tc_summary.append(f"{i}. {tc.get('id', f'TC{i}')}: {tc.get('title', 'Untitled')}")
        
        prompt = f"""You are refining a test plan for a web application.

PAGE BEING TESTED:
URL: {page_structure.get('url', 'Unknown')}

KEY ELEMENTS:
{chr(10).join(elements_summary) if elements_summary else 'No elements extracted'}

FORMS:
{chr(10).join(forms_summary) if forms_summary else 'No forms found'}

CURRENT TEST CASES:
{chr(10).join(current_tc_summary) if current_tc_summary else 'No test cases yet'}

USER REQUEST:
{user_feedback}

Based on the user's request, provide ONLY the NEW or MODIFIED test cases in JSON format.
If adding new tests, generate appropriate test cases.
If modifying existing tests, provide the updated version.
If removing tests, indicate which test IDs to remove.

Respond in this exact JSON format ONLY:
{{
    "action": "add" | "modify" | "remove",
    "test_cases": [
        {{
            "id": "TC_XXX",
            "title": "Test Case Title",
            "priority": "high" | "medium" | "low",
            "type": "functional" | "ui" | "integration",
            "steps": ["Step 1", "Step 2", "..."],
            "expectedResult": "What should happen",
            "elements": ["element selectors used"]
        }}
    ],
    "remove_ids": ["TC_001"]  // only if action is "remove"
}}

Only output valid JSON, no explanations."""

        log("Sending refinement prompt to LLM...")
        result = llm_call(prompt)
        log(f"LLM response received in {result.get('response_time', 0):.2f}s")
        
        # Parse the response
        response_text = result['text'].strip()
        
        # Try to extract JSON from response
        try:
            # Remove markdown code blocks if present
            if '```json' in response_text:
                response_text = response_text.split('```json')[1].split('```')[0]
            elif '```' in response_text:
                response_text = response_text.split('```')[1].split('```')[0]
            
            refinement = json.loads(response_text)
        except json.JSONDecodeError as e:
            log(f"Failed to parse JSON: {e}", "ERROR")
            # Try to find JSON in the response
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                try:
                    refinement = json.loads(json_match.group())
                except:
                    return {
                        'test_cases': current_test_cases,
                        'message': f"I understood your request but couldn't process it properly. Please try rephrasing.",
                        'response_time': result['response_time'],
                        'tokens_used': result['tokens_used']
                    }
            else:
                return {
                    'test_cases': current_test_cases,
                    'message': f"I understood your request but couldn't process it properly. Please try rephrasing.",
                    'response_time': result['response_time'],
                    'tokens_used': result['tokens_used']
                }
        
        # Apply the refinement
        action = refinement.get('action', 'add')
        new_cases = refinement.get('test_cases', [])
        remove_ids = refinement.get('remove_ids', [])
        
        updated_cases = current_test_cases.copy()
        message = ""
        
        if action == 'add' and new_cases:
            # Assign IDs to new cases
            existing_ids = {tc.get('id') for tc in updated_cases}
            for tc in new_cases:
                if not tc.get('id') or tc.get('id') in existing_ids:
                    tc['id'] = f"TC_{len(updated_cases) + 1:03d}"
                updated_cases.append(tc)
                existing_ids.add(tc['id'])
            message = f"✅ Added {len(new_cases)} new test case(s). You now have {len(updated_cases)} test cases total."
            log(f"Added {len(new_cases)} test cases")
            
        elif action == 'modify' and new_cases:
            # Update existing cases by ID
            modified_count = 0
            for new_tc in new_cases:
                tc_id = new_tc.get('id')
                for i, existing_tc in enumerate(updated_cases):
                    if existing_tc.get('id') == tc_id:
                        updated_cases[i] = {**existing_tc, **new_tc}
                        modified_count += 1
                        break
            message = f"✅ Modified {modified_count} test case(s)."
            log(f"Modified {modified_count} test cases")
            
        elif action == 'remove' and remove_ids:
            # Remove cases by ID
            original_count = len(updated_cases)
            updated_cases = [tc for tc in updated_cases if tc.get('id') not in remove_ids]
            removed_count = original_count - len(updated_cases)
            message = f"✅ Removed {removed_count} test case(s). You now have {len(updated_cases)} test cases remaining."
            log(f"Removed {removed_count} test cases")
        else:
            message = "I understood your request but no changes were made. Please be more specific about what you'd like to add, modify, or remove."
        
        # Save updated test cases
        if len(updated_cases) != len(current_test_cases) or action == 'modify':
            test_cases_path = DesignService.save_test_cases(updated_cases, page_structure)
            log(f"Updated test cases saved to: {test_cases_path}")
        
        log("=" * 60)
        
        return {
            'test_cases': updated_cases,
            'message': message,
            'response_time': result['response_time'],
            'tokens_used': result['tokens_used']
        }


# Singleton instance
design_service = DesignService()
