"""
QA Testing Agent - Flask Backend
Main entry point for the Python backend server
"""

from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
import time
import os
import json

from llm.groq_client import GroqClient
from llm.config import LLMConfig
from services.exploration_service import exploration_service, log
from services.design_service import design_service
from services.implementation_service import implementation_service
from services.verification_service import verification_service
from utils.helpers import helpers

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend communication

# Initialize Groq client with configuration
llm_config = LLMConfig(
    max_tokens=5000,
    model_name="openai/gpt-oss-120b",
    reasoning_effort="medium",
    temperature=1.0,
    top_p=1
)
groq_client = GroqClient(llm_config)

# Store session state (in production, use proper session management)
session_state = helpers.create_initial_state()


def llm_call(prompt: str, system_prompt: str = '') -> dict:
    """Wrapper for LLM calls - converts to Groq format and back"""
    start_time = time.time()
    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    try:
        response = groq_client.generate(messages)
        response_time = time.time() - start_time
        
        # Extract text from response
        text = response.get('content', '')
        
        # Estimate tokens (rough approximation)
        tokens_used = len(prompt.split()) + len(text.split())
        
        return {
            'text': text,
            'response_time': response_time,
            'tokens_used': tokens_used
        }
    except Exception as e:
        print(f"[LLM] Error calling Groq: {e}")
        raise


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    # Test Groq connection
    try:
        test_response = groq_client.generate([{"role": "user", "content": "ping"}])
        groq_available = True
    except:
        groq_available = False
    
    return jsonify({
        'status': 'ok',
        'groq_available': groq_available,
        'model': llm_config.model_name,
        'timestamp': time.time()
    })


@app.route('/api/explore', methods=['POST'])
def explore_url():
    """Explore a URL and return page structure"""
    data = request.json
    url = data.get('url')
    
    if not url:
        return jsonify({'error': 'URL is required'}), 400
    
    if not helpers.is_valid_url(url):
        return jsonify({'error': 'Invalid URL format'}), 400
    
    try:
        result = exploration_service.explore(url, llm_call)
        session_state['page_structure'] = result['page_data']
        session_state['phase'] = 'explored'
        
        # Update metrics
        session_state['metrics'] = helpers.update_metrics(
            session_state['metrics'],
            result['response_time'],
            result['tokens_used']
        )
        
        return jsonify({
            'success': True,
            'page_data': result['page_data'],
            'page_model_path': result.get('page_model_path', ''),
            'response_time': result['response_time'],
            'tokens_used': result['tokens_used'],
            'metrics': session_state['metrics']
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/design', methods=['POST'])
def design_tests():
    """Design test cases based on page structure"""
    if not session_state.get('page_structure'):
        return jsonify({'error': 'Please explore a URL first'}), 400
    
    try:
        result = design_service.design(session_state['page_structure'], llm_call)
        session_state['test_cases'] = result['test_cases']
        session_state['phase'] = 'designed'
        
        # Update metrics
        session_state['metrics'] = helpers.update_metrics(
            session_state['metrics'],
            result['response_time'],
            result['tokens_used']
        )
        
        return jsonify({
            'success': True,
            'test_cases': result['test_cases'],
            'test_cases_path': result.get('test_cases_path', ''),
            'response_time': result['response_time'],
            'tokens_used': result['tokens_used'],
            'metrics': session_state['metrics']
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/implement', methods=['POST'])
def implement_tests():
    """Implement test code based on test cases"""
    if not session_state.get('test_cases'):
        return jsonify({'error': 'Please design test cases first'}), 400
    
    try:
        result = implementation_service.implement(
            session_state['test_cases'],
            session_state['page_structure'],
            llm_call
        )
        session_state['generated_code'] = result['code']
        session_state['test_file_path'] = result.get('file_path', '')  # Store for verification
        session_state['phase'] = 'implemented'
        
        # Update metrics
        session_state['metrics'] = helpers.update_metrics(
            session_state['metrics'],
            result['response_time'],
            result['tokens_used']
        )
        
        return jsonify({
            'success': True,
            'code': result['code'],
            'file_path': result.get('file_path', ''),
            'self_correction': result.get('self_correction', {}),
            'response_time': result['response_time'],
            'tokens_used': result['tokens_used'],
            'metrics': session_state['metrics']
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/verify', methods=['POST'])
def verify_tests():
    """Verify tests by actually running them with video evidence"""
    if not session_state.get('generated_code'):
        return jsonify({'error': 'Please implement tests first'}), 400
    
    try:
        # Get the test file path from the implementation phase
        test_file_path = session_state.get('test_file_path')
        
        result = verification_service.verify(
            session_state['generated_code'],
            session_state['test_cases'],
            llm_call,
            test_file_path
        )
        
        session_state['phase'] = 'verified'
        session_state['last_verification'] = result  # Store for critique
        session_state['test_file_path'] = result.get('test_file')
        
        # Update metrics
        session_state['metrics'] = helpers.update_metrics(
            session_state['metrics'],
            result['response_time'],
            result['tokens_used']
        )
        
        return jsonify({
            'success': True,
            'report': result['report'],
            'evidence': result['report'].get('evidence', {}),
            'execution_details': result['report'].get('execution_details', {}),
            'response_time': result['response_time'],
            'tokens_used': result['tokens_used'],
            'metrics': session_state['metrics']
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/verify-stream', methods=['POST'])
def verify_tests_streaming():
    """Verify tests with real-time streaming of results via Server-Sent Events"""
    if not session_state.get('generated_code'):
        return jsonify({'error': 'Please implement tests first'}), 400
    
    def generate():
        try:
            # Get the test file path
            test_file_path = session_state.get('test_file_path')
            
            if not test_file_path:
                # Find the most recent test file
                from pathlib import Path
                tests_dir = Path(__file__).parent / 'tests'
                test_files = sorted(tests_dir.glob("test_*.py"), key=lambda f: f.stat().st_mtime, reverse=True)
                if test_files:
                    test_file_path = str(test_files[0])
                else:
                    yield f"data: {json.dumps({'event': 'error', 'data': {'error': 'No test files found'}})}\n\n"
                    return
            
            # Stream test results
            for event in verification_service.run_pytest_streaming(test_file_path):
                yield f"data: {json.dumps(event)}\n\n"
                
                # If complete, update session state
                if event.get('event') == 'complete':
                    session_state['phase'] = 'verified'
                    session_state['test_file_path'] = test_file_path
                    session_state['last_verification'] = {
                        'execution_result': event['data'],
                        'test_file': test_file_path
                    }
        except Exception as e:
            import traceback
            traceback.print_exc()
            yield f"data: {json.dumps({'event': 'error', 'data': {'error': str(e)}})}\n\n"
    
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )


@app.route('/api/critique', methods=['POST'])
def critique_tests():
    """Handle user critique and refactor tests based on feedback"""
    data = request.json
    critique = data.get('critique', '').strip()
    
    if not critique:
        return jsonify({'error': 'Critique message is required'}), 400
    
    if not session_state.get('last_verification'):
        return jsonify({'error': 'Please run verification first'}), 400
    
    try:
        result = verification_service.handle_critique(
            critique=critique,
            code=session_state['generated_code'],
            test_results=session_state['last_verification'],
            page_structure=session_state.get('page_structure', {}),
            llm_call=llm_call
        )
        
        # Update session state with refactored code
        session_state['generated_code'] = result['refactored_code']
        session_state['test_file_path'] = result['new_file_path']
        session_state['last_verification'] = {
            'execution_result': result['execution_result'],
            'test_file': result['new_file_path']
        }
        
        # Update metrics
        session_state['metrics'] = helpers.update_metrics(
            session_state['metrics'],
            result['response_time'],
            result['tokens_used']
        )
        
        # Build response
        passed_before = result['improvement']['original_passed']
        passed_after = result['improvement']['new_passed']
        
        return jsonify({
            'success': True,
            'message': f'Tests refactored based on your critique. Results: {passed_after} tests passing (was {passed_before})',
            'refactored_code': result['refactored_code'],
            'new_file_path': result['new_file_path'],
            'execution_result': {
                'success': result['execution_result'].get('success', False),
                'passed': passed_after,
                'duration': result['execution_result'].get('duration', 0)
            },
            'evidence': {
                'video_files': result['execution_result'].get('video_files', []),
                'report_path': result['evidence_report'].get('report_path', '')
            },
            'improvement': result['improvement'],
            'response_time': result['response_time'],
            'tokens_used': result['tokens_used'],
            'metrics': session_state['metrics']
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/evidence', methods=['GET'])
def get_evidence():
    """Get list of evidence files (videos and reports)"""
    evidence_dir = os.path.join(os.path.dirname(__file__), 'evidence')
    
    if not os.path.exists(evidence_dir):
        return jsonify({
            'success': True,
            'videos': [],
            'reports': [],
            'evidence_dir': evidence_dir
        })
    
    videos = []
    reports = []
    
    for root, dirs, files in os.walk(evidence_dir):
        for file in files:
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, evidence_dir)
            
            if file.endswith('.webm'):
                videos.append({
                    'name': file,
                    'path': file_path,
                    'relative_path': rel_path,
                    'size': os.path.getsize(file_path)
                })
            elif file.endswith('.json'):
                reports.append({
                    'name': file,
                    'path': file_path,
                    'relative_path': rel_path
                })
    
    return jsonify({
        'success': True,
        'videos': videos,
        'reports': reports,
        'evidence_dir': evidence_dir
    })


@app.route('/api/chat', methods=['POST'])
def chat():
    """Context-aware chat with the LLM - handles refinement requests"""
    data = request.json
    message = data.get('message', '').strip()
    
    if not message:
        return jsonify({'error': 'Message is required'}), 400
    
    try:
        message_lower = message.lower()
        current_phase = session_state.get('phase', 'idle')
        
        # Check if this is a test case refinement request during design phase
        is_test_case_request = any(keyword in message_lower for keyword in [
            'add test', 'add more test', 'create test', 'new test',
            'remove test', 'delete test', 'modify test', 'change test', 'remove', 'delete',
            'update test', 'edit test', 'add case', 'more cases'
        ])
        
        if is_test_case_request and session_state.get('page_structure'):
            log("[Chat] Handling test case refinement request...")
            # Handle test case refinement with context
            result = design_service.refine_test_cases(
                user_feedback=message,
                current_test_cases=session_state.get('test_cases', []),
                page_structure=session_state['page_structure'],
                llm_call=llm_call
            )
            
            session_state['test_cases'] = result['test_cases']
            session_state['phase'] = 'designed'
            
            # Update metrics
            session_state['metrics'] = helpers.update_metrics(
                session_state['metrics'],
                result['response_time'],
                result['tokens_used']
            )
            
            return jsonify({
                'success': True,
                'response': result['message'],
                'test_cases': result['test_cases'],
                'action_taken': 'refine_test_cases',
                'response_time': result['response_time'],
                'tokens_used': result['tokens_used'],
                'metrics': session_state['metrics']
            })
        
        # Build context-aware system prompt
        context_parts = ['You are a helpful QA testing assistant.']
        
        if current_phase != 'idle':
            context_parts.append(f'\nCurrent phase: {current_phase}')
        
        if session_state.get('page_structure'):
            page_info = session_state['page_structure']
            context_parts.append(f'\nCurrently exploring: {page_info.get("url", "a webpage")}')
            context_parts.append(f'Elements found: {len(page_info.get("elements", []))}')
        
        if session_state.get('test_cases'):
            tc_count = len(session_state['test_cases'])
            tc_titles = [tc.get('title', 'Untitled') for tc in session_state['test_cases'][:5]]
            context_parts.append(f'\nCurrent test cases ({tc_count}): {", ".join(tc_titles)}')
            if tc_count > 5:
                context_parts.append(f'... and {tc_count - 5} more')
        
        system_prompt = '\n'.join(context_parts)
        
        result = llm_call(message, system_prompt)
        
        # Update metrics
        session_state['metrics'] = helpers.update_metrics(
            session_state['metrics'],
            result['response_time'],
            result['tokens_used']
        )
        
        return jsonify({
            'success': True,
            'response': result['text'],
            'response_time': result['response_time'],
            'tokens_used': result['tokens_used'],
            'metrics': session_state['metrics']
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/reset', methods=['POST'])
def reset_session():
    """Reset the session state"""
    global session_state
    session_state = helpers.create_initial_state()
    
    return jsonify({
        'success': True,
        'message': 'Session reset successfully'
    })


@app.route('/api/state', methods=['GET'])
def get_state():
    """Get current session state"""
    suggestion = helpers.get_suggested_action(session_state['phase'])
    
    return jsonify({
        'phase': session_state['phase'],
        'has_page_structure': session_state['page_structure'] is not None,
        'test_cases_count': len(session_state.get('test_cases', [])),
        'has_generated_code': bool(session_state.get('generated_code')),
        'metrics': session_state['metrics'],
        'suggested_action': suggestion['action'],
        'suggestion_message': suggestion['message']
    })


@app.route('/api/determine-action', methods=['POST'])
def determine_action():
    """Determine what action to take based on user input and current phase"""
    data = request.json
    user_input = data.get('input', '')
    
    action = helpers.determine_action(user_input, session_state)
    suggestion = helpers.get_suggested_action(session_state['phase'])
    
    return jsonify({
        'action': action,
        'current_phase': session_state['phase'],
        'suggested_action': suggestion['action'],
        'suggestion_message': suggestion['message']
    })


@app.route('/api/code', methods=['GET'])
def get_code():
    """Get generated code"""
    return jsonify({
        'code': session_state.get('generated_code', ''),
        'has_code': bool(session_state.get('generated_code'))
    })


if __name__ == '__main__':
    print("=" * 50)
    print("QA Testing Agent - Backend Server")
    print("=" * 50)
    print("\nStarting server on http://localhost:5000")
    print(f"\nUsing Groq LLM:")
    print(f"  - Model: {llm_config.model_name}")
    print(f"  - Temperature: {llm_config.temperature}")
    print(f"  - Max Tokens: {llm_config.max_tokens}")
    print("\nMake sure GROQ_API_KEY is set in .env file")
    print("\n" + "=" * 50)
    
    app.run(debug=True, port=5000)
