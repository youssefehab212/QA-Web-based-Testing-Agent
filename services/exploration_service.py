"""
Exploration Service
Handles URL exploration and page structure analysis using real browser automation
"""

import json
import os
import re
import traceback
from datetime import datetime
from typing import Dict, Any, Callable
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# Output directory for JSON files
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'output')


def log(message: str, level: str = "INFO"):
    """Print a formatted log message with timestamp"""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] [{level}] [Exploration] {message}")


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


class ExplorationService:
    """Service for exploring URLs and analyzing page structure"""
    
    @staticmethod
    def save_page_model(page_data: Dict[str, Any], url: str) -> str:
        """
        Save the page model to a JSON file
        
        Args:
            page_data: The page structure data
            url: The URL that was explored
            
        Returns:
            Path to the saved file
        """
        ensure_output_dir()
        
        domain = get_domain_from_url(url)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"page_model_{domain}_{timestamp}.json"
        filepath = os.path.join(OUTPUT_DIR, filename)
        
        # Create a comprehensive page model
        page_model = {
            "metadata": {
                "url": url,
                "timestamp": datetime.now().isoformat(),
                "title": page_data.get('pageMetadata', {}).get('title', 'Unknown'),
                "type": page_data.get('pageMetadata', {}).get('type', 'generic'),
                "complexity": page_data.get('pageMetadata', {}).get('complexity', 'medium')
            },
            "elements": page_data.get('elements', []),
            "userFlows": page_data.get('userFlows', []),
            "raw_dom": page_data.get('raw_dom', {}),
            "pageMetadata": page_data.get('pageMetadata', {})
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(page_model, f, indent=2, ensure_ascii=False)
        
        log(f"Page model saved to: {filepath}")
        return filepath
    
    @staticmethod
    def fetch_page_dom(url: str) -> Dict[str, Any]:
        """
        Actually visit the URL and extract DOM information using Playwright
        
        Args:
            url: The URL to explore
            
        Returns:
            Extracted page information
        """
        log(f"========== STARTING DOM FETCH ==========")
        log(f"Target URL: {url}")
        
        log("Initializing Playwright...")
        with sync_playwright() as p:
            log("Playwright initialized successfully")
            
            log("Launching Chromium browser (headless mode)...")
            browser = p.chromium.launch(headless=True)
            log("Browser launched successfully")
            
            log("Creating new browser page...")
            page = browser.new_page()
            log("New page created")
            
            try:
                log(f"Navigating to URL: {url}")
                log("Waiting for page to load (timeout: 30s)...")
                page.goto(url, timeout=30000)
                log("Initial navigation complete")
                
                log("Waiting for DOM content to be loaded (timeout: 15s)...")
                page.wait_for_load_state('domcontentloaded', timeout=15000)
                log("DOM content loaded successfully")
            except PlaywrightTimeout as e:
                log(f"Timeout occurred (continuing with partial load): {e}", "WARN")
            except Exception as e:
                log(f"Navigation error: {e}", "ERROR")
                log(f"Traceback: {traceback.format_exc()}", "ERROR")
            
            # Extract page title
            log("Extracting page title...")
            title = page.title()
            log(f"Page title: '{title}'")
            
            # Extract all interactive elements using compatible JavaScript
            log("Extracting interactive elements via JavaScript...")
            log("Searching for: buttons, inputs, selects, textareas, links, [role=button], [onclick], forms")
            
            elements = page.evaluate('''() => {
                const elements = [];
                
                // Get all interactive elements
                const selectors = [
                    'button', 'input', 'select', 'textarea', 'a[href]',
                    '[role="button"]', '[onclick]', 'form'
                ];
                
                selectors.forEach(selector => {
                    document.querySelectorAll(selector).forEach(el => {
                        try {
                            const rect = el.getBoundingClientRect();
                            if (rect.width > 0 && rect.height > 0) {
                                const text = el.innerText || el.textContent || '';
                                elements.push({
                                    tag: el.tagName.toLowerCase(),
                                    type: el.type || el.getAttribute('role') || el.tagName.toLowerCase(),
                                    id: el.id || null,
                                    name: el.name || null,
                                    className: (typeof el.className === 'string') ? el.className : null,
                                    text: text.substring(0, 50).trim() || null,
                                    placeholder: el.placeholder || null,
                                    href: el.href || null,
                                    locator: el.id ? '#' + el.id : 
                                             el.name ? '[name="' + el.name + '"]' :
                                             (typeof el.className === 'string' && el.className) ? '.' + el.className.split(' ')[0] : 
                                             el.tagName.toLowerCase()
                                });
                            }
                        } catch (e) {
                            // Skip problematic elements
                        }
                    });
                });
                
                return elements;
            }''')
            
            log(f"Found {len(elements)} interactive elements")
            if elements:
                log(f"Element breakdown:")
                # Count by tag
                tag_counts = {}
                for el in elements:
                    tag = el.get('tag', 'unknown')
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1
                for tag, count in tag_counts.items():
                    log(f"  - {tag}: {count}")
                
                # Show all elements
                log(f"Elements found:")
                for i, el in enumerate(elements[:5]):
                    text = (el.get('text') or '')[:20]
                    log(f"  [{i+1}] {el.get('tag')} | id={el.get('id')} | text='{text}'")
            
            # Extract forms
            log("Extracting form elements...")
            forms = page.evaluate('''() => {
                return Array.from(document.querySelectorAll('form')).map(form => ({
                    id: form.id || null,
                    action: form.action || null,
                    method: form.method || 'get',
                    inputs: Array.from(form.querySelectorAll('input, select, textarea')).map(input => ({
                        type: input.type || input.tagName.toLowerCase(),
                        name: input.name || null,
                        id: input.id || null,
                        required: input.required || false
                    }))
                }));
            }''')
            
            log(f"Found {len(forms)} forms")
            for i, form in enumerate(forms):
                log(f"  Form [{i+1}]: id={form.get('id')} | action={form.get('action')} | inputs={len(form.get('inputs', []))}")
            
            # Get page HTML structure (simplified)
            log("Extracting HTML snippet (first 5000 chars)...")
            html_structure = page.evaluate('''() => {
                return document.body ? document.body.innerHTML.substring(0, 5000) : '';
            }''')
            log(f"HTML snippet extracted: {len(html_structure)} characters")
            
            log("Closing browser...")
            browser.close()
            log("Browser closed")
            
            result = {
                'title': title,
                'url': url,
                'elements': elements,
                'forms': forms,
                'html_snippet': html_structure
            }
            
            log(f"========== DOM FETCH COMPLETE ==========")
            log(f"Summary: {len(elements)} elements, {len(forms)} forms, title='{title}'")
            return result
    
    @staticmethod
    def generate_prompt(url: str, dom_data: Dict[str, Any]) -> str:
        """
        Generate the exploration prompt with REAL DOM data
        
        Args:
            url: The URL explored
            dom_data: Actual DOM data from the page
            
        Returns:
            The exploration prompt
        """
        log("Generating LLM prompt with DOM data...")
        log(f"  - URL: {url}")
        log(f"  - Title: {dom_data.get('title', 'Unknown')}")
        log(f"  - Total elements available: {len(dom_data.get('elements', []))}")
        log(f"  - Elements to include in prompt: {min(20, len(dom_data.get('elements', [])))}")
        log(f"  - Forms to include: {len(dom_data.get('forms', []))}")
        
        prompt = f'''You are a web testing agent. I have visited this URL: {url}

Here is the ACTUAL page data extracted from the DOM:

Page Title: {dom_data.get('title', 'Unknown')}

Interactive Elements Found ({len(dom_data.get('elements', []))} elements):
{json.dumps(dom_data.get('elements', [])[:20], indent=2)}

Forms Found:
{json.dumps(dom_data.get('forms', []), indent=2)}

Based on this REAL page structure, generate a structured analysis. Return ONLY a JSON object:
{{
  "url": "{url}",
  "elements": [
    {{
      "type": "button|input|link|form|etc",
      "locator": "CSS selector or ID (use the actual locators from above)",
      "description": "What this element does",
      "interactions": ["click", "type", "hover"],
      "testable": true/false
    }}
  ],
  "userFlows": [
    {{
      "name": "Flow name",
      "steps": ["Step 1", "Step 2"],
      "priority": "high|medium|low"
    }}
  ],
  "pageMetadata": {{
    "title": "{dom_data.get('title', 'Unknown')}",
    "type": "login|form|dashboard|e-commerce|etc",
    "complexity": "simple|medium|complex"
  }}
}}

Analyze the actual elements and create meaningful test flows.'''
        
        log(f"Prompt generated: {len(prompt)} characters")
        return prompt

    @staticmethod
    def parse_response(response_text: str, url: str) -> Dict[str, Any]:
        """
        Parse the exploration response
        
        Args:
            response_text: Raw response from LLM
            url: Original URL
            
        Returns:
            Parsed page structure
        """
        log("========== PARSING LLM RESPONSE ==========")
        log(f"Raw response length: {len(response_text)} characters")
        log(f"Response preview (first 200 chars): {response_text[:200]}...")
        
        try:
            # Remove markdown code blocks if present
            log("Cleaning response (removing markdown code blocks)...")
            clean_text = re.sub(r'```json|```', '', response_text).strip()
            log(f"Cleaned text length: {len(clean_text)} characters")
            
            log("Attempting to parse as JSON...")
            parsed = json.loads(clean_text)
            log(f"JSON parsed successfully!")
            log(f"Parsed object keys: {list(parsed.keys())}")
            log(f"Elements in parsed response: {len(parsed.get('elements', []))}")
            log(f"User flows in parsed response: {len(parsed.get('userFlows', []))}")
            return parsed
        except json.JSONDecodeError as e:
            log(f"JSON parse error: {e}", "ERROR")
            log(f"Problematic text around error: {clean_text[max(0, e.pos-50):e.pos+50]}", "ERROR")
            log("Returning default structure", "WARN")
            return ExplorationService.get_default_structure(url)
        except Exception as e:
            log(f"Unexpected error during parsing: {e}", "ERROR")
            log(f"Traceback: {traceback.format_exc()}", "ERROR")
            return ExplorationService.get_default_structure(url)
    
    @staticmethod
    def get_default_structure(url: str) -> Dict[str, Any]:
        """
        Get default page structure when parsing fails
        
        Args:
            url: The URL
            
        Returns:
            Default page structure
        """
        log("Creating default page structure (parsing failed)", "WARN")
        return {
            "url": url,
            "elements": [],
            "userFlows": [],
            "pageMetadata": {"title": "Web Page", "type": "generic", "complexity": "medium"}
        }
    
    @staticmethod
    def explore(url: str, llm_call: Callable) -> Dict[str, Any]:
        """
        Explore a URL using REAL browser automation and return page structure
        
        Args:
            url: URL to explore
            llm_call: LLM call function
            
        Returns:
            Exploration result with page_data, response_time, and tokens_used
        """
        log("=" * 60)
        log("========== STARTING EXPLORATION PHASE ==========")
        log("=" * 60)
        log(f"URL to explore: {url}")
        
        # Step 1: Actually visit the page and extract DOM
        log("")
        log(">>> STEP 1: DOM EXTRACTION <<<")
        dom_data = None
        try:
            dom_data = ExplorationService.fetch_page_dom(url)
            log(f"DOM extraction successful!")
            log(f"  - Elements found: {len(dom_data.get('elements', []))}")
            log(f"  - Forms found: {len(dom_data.get('forms', []))}")
            log(f"  - Page title: {dom_data.get('title', 'N/A')}")
        except Exception as e:
            log(f"DOM extraction FAILED: {e}", "ERROR")
            log(f"Traceback: {traceback.format_exc()}", "ERROR")
            log("Using empty fallback data", "WARN")
            dom_data = {'title': 'Unknown', 'url': url, 'elements': [], 'forms': []}
        
        # Step 2: Generate prompt with DOM data
        log("")
        log(">>> STEP 2: GENERATING LLM PROMPT <<<")
        prompt = ExplorationService.generate_prompt(url, dom_data)
        log(f"Prompt generated successfully")
        log(f"  - Prompt length: {len(prompt)} characters")
        log(f"  - Elements included in prompt: {min(20, len(dom_data.get('elements', [])))}")
        
        # Step 3: Send to LLM
        log("")
        log(">>> STEP 3: CALLING LLM <<<")
        log("Sending prompt...")
        result = llm_call(prompt)
        log(f"LLM response received!")
        log(f"  - Response time: {result.get('response_time', 0):.2f}s")
        log(f"  - Tokens used: {result.get('tokens_used', 0)}")
        log(f"  - Response text length: {len(result.get('text', ''))} characters")
        
        # Step 4: Parse response
        log("")
        log(">>> STEP 4: PARSING RESPONSE <<<")
        page_data = ExplorationService.parse_response(result['text'], url)
        
        # Include raw DOM data for reference
        page_data['raw_dom'] = {
            'element_count': len(dom_data.get('elements', [])),
            'form_count': len(dom_data.get('forms', [])),
            'elements': dom_data.get('elements', [])[:30]  # Include first 30 elements for reference
        }
        
        # Step 5: Save page model to JSON file
        log("")
        log(">>> STEP 5: SAVING PAGE MODEL <<<")
        page_model_path = ExplorationService.save_page_model(page_data, url)
        
        # Final summary
        log("")
        log(">>> EXPLORATION COMPLETE <<<")
        log(f"  - LLM analyzed elements: {len(page_data.get('elements', []))}")
        log(f"  - User flows identified: {len(page_data.get('userFlows', []))}")
        log(f"  - Raw DOM elements: {page_data['raw_dom']['element_count']}")
        log(f"  - Raw DOM forms: {page_data['raw_dom']['form_count']}")
        log(f"  - Page type: {page_data.get('pageMetadata', {}).get('type', 'unknown')}")
        log(f"  - Page model saved to: {page_model_path}")
        log("=" * 60)
        
        return {
            'page_data': page_data,
            'page_model_path': page_model_path,
            'response_time': result['response_time'],
            'tokens_used': result['tokens_used']
        }


# Singleton instance
exploration_service = ExplorationService()
