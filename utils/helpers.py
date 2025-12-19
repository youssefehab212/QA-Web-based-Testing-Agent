"""
Utility Helper Functions
"""

import re
from datetime import datetime
from typing import Dict, Any

from services.design_service import log


class Helpers:
    """Collection of utility helper functions"""
    
    @staticmethod
    def is_valid_url(string: str) -> bool:
        """
        Check if a string is a valid URL
        
        Args:
            string: String to check
            
        Returns:
            True if valid URL, False otherwise
        """
        return bool(re.match(r'^https?://', string))
    
    @staticmethod
    def format_time(timestamp: float) -> str:
        """
        Format timestamp to readable string
        
        Args:
            timestamp: Unix timestamp
            
        Returns:
            Formatted time string
        """
        return datetime.fromtimestamp(timestamp).strftime('%H:%M:%S')
    
    @staticmethod
    def create_initial_state() -> Dict[str, Any]:
        """
        Create initial state for the agent
        
        Returns:
            Initial state dictionary
        """
        return {
            'messages': [],
            'input': '',
            'loading': False,
            'phase': 'idle',
            'page_structure': None,
            'test_cases': [],
            'generated_code': '',
            'metrics': {
                'avg_response_time': 0,
                'tokens_used': 0,
                'iteration_count': 0
            },
            'browser_view': ''
        }
    
    @staticmethod
    def update_metrics(current_metrics: Dict[str, Any], response_time: int, tokens: int) -> Dict[str, Any]:
        """
        Calculate updated metrics
        
        Args:
            current_metrics: Current metrics
            response_time: New response time in ms
            tokens: Tokens used
            
        Returns:
            Updated metrics
        """
        log("Updating metrics...")
        log(f"Current metrics: {current_metrics}")
        log(f"New response time: {response_time} ms, Tokens used: {tokens}")

        iteration_count = current_metrics.get('iteration_count', 0)
        avg_response_time = current_metrics.get('avg_response_time', 0)
        
        if iteration_count == 0:
            new_avg = response_time
        else:
            new_avg = (avg_response_time * iteration_count + response_time) / (iteration_count + 1)
        
        return {
            'avg_response_time': new_avg,
            'tokens_used': current_metrics.get('tokens_used', 0) + tokens,
            'iteration_count': iteration_count + 1
        }
    
    @staticmethod
    def determine_action(user_input: str, current_state: Dict[str, Any] = None) -> str:
        """
        Determine action from user input, considering current phase
        
        Args:
            user_input: User input string
            current_state: Current session state (optional)
            
        Returns:
            Action type: 'explore', 'design', 'implement', 'verify', or 'chat'
        """
        lower_input = user_input.lower()
        
        # Get current phase and state info
        phase = current_state.get('phase', 'idle') if current_state else 'idle'
        has_page_structure = current_state.get('page_structure') is not None if current_state else False
        has_test_cases = len(current_state.get('test_cases', [])) > 0 if current_state else False
        has_code = bool(current_state.get('generated_code')) if current_state else False
        
        # 1. Explicit URL always means explore
        if Helpers.is_valid_url(user_input):
            return 'explore'
        
        # 2. Explicit action keywords override phase logic
        explicit_actions = {
            'explore': ['explore', 'visit', 'navigate', 'open', 'go to', 'analyze url', 'scan'],
            'design': ['design', 'test case', 'create tests', 'generate tests', 'plan tests', 'write tests'],
            'implement': ['implement', 'generate code', 'write code', 'create code', 'playwright', 'automation'],
            'verify': ['verify', 'run tests', 'execute', 'validate', 'check tests', 'run code']
        }
        
        for action, keywords in explicit_actions.items():
            if any(kw in lower_input for kw in keywords):
                # Validate that the action is possible given current state
                if action == 'design' and not has_page_structure:
                    return 'chat'  # Can't design without exploration
                if action == 'implement' and not has_test_cases:
                    return 'chat'  # Can't implement without test cases
                if action == 'verify' and not has_code:
                    return 'chat'  # Can't verify without code
                return action
        
        # 3. Smart phase-based suggestions for ambiguous inputs
        # Keywords that suggest "continue" or "next step"
        continue_keywords = ['next', 'continue', 'proceed', 'go ahead', 'yes', 'ok', 'sure', 
                            'do it', "let's go", 'start', 'begin', 'ready']
        
        if any(kw in lower_input for kw in continue_keywords):
            # Suggest the next logical action based on current phase
            if phase == 'idle':
                return 'chat'  # Need a URL first
            elif phase == 'explored':
                return 'design'  # Next step after exploration
            elif phase == 'designed':
                return 'implement'  # Next step after design
            elif phase == 'implemented':
                return 'verify'  # Next step after implementation
            elif phase == 'verified':
                return 'chat'  # Workflow complete, open to chat
        
        # 4. Phase-specific default responses
        # If user says something vague, suggest based on phase
        if phase == 'exploring':
            return 'chat'  # Wait for exploration to complete
        elif phase == 'designing':
            return 'chat'  # Wait for design to complete
        elif phase == 'implementing':
            return 'chat'  # Wait for implementation to complete
        elif phase == 'verifying':
            return 'chat'  # Wait for verification to complete
        
        # 5. Default to chat for anything else
        return 'chat'
    
    @staticmethod
    def get_suggested_action(phase: str) -> Dict[str, str]:
        """
        Get the suggested next action based on current phase
        
        Args:
            phase: Current phase
            
        Returns:
            Dictionary with action and suggestion message
        """
        suggestions = {
            'idle': {
                'action': 'explore',
                'message': 'Enter a URL to start exploring'
            },
            'explored': {
                'action': 'design',
                'message': 'Ready to design test cases. Say "design tests" or click Design.'
            },
            'designed': {
                'action': 'implement',
                'message': 'Test cases ready. Say "implement" to generate Playwright code.'
            },
            'implemented': {
                'action': 'verify',
                'message': 'Code generated. Say "verify" to validate the tests.'
            },
            'verified': {
                'action': 'complete',
                'message': 'Workflow complete! Download the code or start a new session.'
            }
        }
        
        return suggestions.get(phase, {'action': 'chat', 'message': 'How can I help you?'})


# Singleton instance
helpers = Helpers()
