// Main Application Component
// Communicates with Python backend via API calls

const API_BASE_URL = 'http://localhost:5000/api';

const TestingAgent = () => {
    const { useState, useRef, useEffect } = React;
    
    // State
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const [phase, setPhase] = useState('idle');
    const [pageStructure, setPageStructure] = useState(null);
    const [testCases, setTestCases] = useState([]);
    const [generatedCode, setGeneratedCode] = useState('');
    const [metrics, setMetrics] = useState({
        avgResponseTime: 0,
        tokensUsed: 0,
        iterationCount: 0
    });
    const [browserView, setBrowserView] = useState('');
    const [backendStatus, setBackendStatus] = useState('checking');
    const messagesEndRef = useRef(null);

    // Check backend health on mount
    useEffect(() => {
        checkBackendHealth();
    }, []);

    const checkBackendHealth = async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/health`);
            if (response.ok) {
                const data = await response.json();
                // Check for either groq_available or ollama_available for backwards compatibility
                const llmAvailable = data.groq_available || data.ollama_available;
                setBackendStatus(llmAvailable ? 'connected' : 'api_missing');
            } else {
                setBackendStatus('disconnected');
            }
        } catch (error) {
            setBackendStatus('disconnected');
        }
    };

    // Auto-scroll to bottom
    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(scrollToBottom, [messages]);

    // Message handling
    const addMessage = (role, content, data = null) => {
        setMessages(prev => [...prev, { role, content, data, timestamp: Date.now() }]);
    };

    // Update metrics from API response
    const updateMetricsFromResponse = (apiMetrics) => {
        if (apiMetrics) {
            setMetrics({
                avgResponseTime: apiMetrics.avg_response_time || 0,
                tokensUsed: apiMetrics.tokens_used || 0,
                iterationCount: apiMetrics.iteration_count || 0
            });
        }
    };

    // API call helper
    const apiCall = async (endpoint, method = 'POST', body = null) => {
        const options = {
            method,
            headers: { 'Content-Type': 'application/json' }
        };
        if (body) {
            options.body = JSON.stringify(body);
        }
        
        const response = await fetch(`${API_BASE_URL}${endpoint}`, options);
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'API request failed');
        }
        
        return data;
    };

    // Explore URL
    const exploreURL = async (url) => {
        setPhase('exploring');
        addMessage('user', `Explore: ${url}`);
        addMessage('assistant', '🔍 Starting exploration phase...');
        setBrowserView(`Loading ${url}...`);

        try {
            const result = await apiCall('/explore', 'POST', { url });
            
            setPageStructure(result.page_data);
            updateMetricsFromResponse(result.metrics);
            setBrowserView(`Explored: ${url}\nFound ${result.page_data.elements?.length || 0} elements`);
            
            addMessage('assistant', 
                `✅ Exploration complete!\n\nFound:\n• ${result.page_data.elements?.length || 0} testable elements\n• ${result.page_data.userFlows?.length || 0} user flows\n• Page complexity: ${result.page_data.pageMetadata?.complexity || 'medium'}`, 
                result.page_data
            );
            setPhase('explored');
        } catch (error) {
            addMessage('assistant', '❌ Exploration failed: ' + error.message);
            setPhase('idle');
        }
    };

    // Design test cases
    const designTests = async () => {
        if (!pageStructure) {
            addMessage('assistant', '⚠️ Please explore a URL first!');
            return;
        }

        setPhase('designing');
        addMessage('user', 'Design test cases');
        addMessage('assistant', '📋 Generating test cases...');

        try {
            const result = await apiCall('/design', 'POST');
            
            setTestCases(result.test_cases);
            updateMetricsFromResponse(result.metrics);
            addMessage('assistant', 
                `✅ Generated ${result.test_cases.length} test cases!\n\nReview them and let me know if you want to add, remove, or modify any.`, 
                result.test_cases
            );
            setPhase('designed');
        } catch (error) {
            addMessage('assistant', '❌ Test design failed: ' + error.message);
            setPhase('explored');
        }
    };

    // Implement tests
    const implementTests = async () => {
        if (!testCases.length) {
            addMessage('assistant', '⚠️ Please design test cases first!');
            return;
        }

        setPhase('implementing');
        addMessage('user', 'Implement test code');
        addMessage('assistant', '💻 Generating Playwright test code...');

        try {
            const result = await apiCall('/implement', 'POST');
            
            setGeneratedCode(result.code);
            updateMetricsFromResponse(result.metrics);
            
            // Show file path if available
            let message = `✅ Test code generated!\n\n${testCases.length} tests implemented in Python + Playwright.`;
            if (result.file_path) {
                message += `\n\n📁 **Saved to:** \`${result.file_path}\``;
            }
            
            addMessage('assistant', message, { code: result.code });
            setPhase('implemented');
        } catch (error) {
            addMessage('assistant', '❌ Implementation failed: ' + error.message);
            setPhase('designed');
        }
    };

    // Verify tests with real-time streaming
    const verifyTests = async () => {
        if (!generatedCode) {
            addMessage('assistant', '⚠️ Please implement tests first!');
            return;
        }

        setPhase('verifying');
        addMessage('user', 'Verify and run tests');
        addMessage('assistant', '🧪 Running tests...');
        setBrowserView('Running tests...');

        try {
            // Use streaming endpoint for real-time updates
            const response = await fetch(`${API_BASE_URL}/verify-stream`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });

            if (!response.ok) {
                throw new Error('Failed to start verification');
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            let testResults = [];
            let finalReport = null;

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';  // Keep incomplete line in buffer

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const event = JSON.parse(line.slice(6));
                            
                            if (event.event === 'test_result') {
                                const { display_name, status, passed } = event.data;
                                const emoji = passed ? '✅' : '❌';
                                const statusText = status.toUpperCase();
                                
                                // Add message for each test result
                                addMessage('assistant', `${emoji} **${display_name}**: ${statusText}`);
                                testResults.push(event.data);
                                
                                // Update browser view with running count
                                const passedCount = testResults.filter(t => t.passed).length;
                                const failedCount = testResults.length - passedCount;
                                setBrowserView(`Running tests...\n\n${testResults.length} completed\n✅ ${passedCount} passed\n❌ ${failedCount} failed`);
                            } else if (event.event === 'complete') {
                                finalReport = event.data;
                            } else if (event.event === 'error') {
                                throw new Error(event.data.error);
                            }
                        } catch (parseError) {
                            console.error('Failed to parse SSE event:', parseError);
                        }
                    }
                }
            }

            // Final summary message
            if (finalReport) {
                const { passed, failed, total, duration } = finalReport;
                setBrowserView(`Test Execution Complete\n\nStatus: ${failed === 0 ? 'PASSED' : 'FAILED'}\n${total} tests executed\n✅ ${passed} passed\n❌ ${failed} failed\n⏱️ ${duration.toFixed(2)}s`);
                addMessage('assistant', 
                    `\n📊 **Verification Summary**\n\nExecuted ${total} tests: ${passed} passed, ${failed} failed\nDuration: ${duration.toFixed(2)}s\nStatus: ${failed === 0 ? '✅ All tests passed!' : '❌ Some tests failed'}`,
                    { tests: testResults, ...finalReport }
                );
            }
            
            setPhase('verified');
        } catch (error) {
            addMessage('assistant', '❌ Verification failed: ' + error.message);
            setPhase('implemented');
        }
    };

    // Handle send
    const handleSend = async () => {
        if (!input.trim() || loading) return;

        const userInput = input.trim();
        setInput('');
        setLoading(true);

        try {
            // Determine action based on input
            if (/^https?:\/\//.test(userInput)) {
                await exploreURL(userInput);
            } else if (userInput.toLowerCase().includes('design') || 
                       (userInput.toLowerCase().includes('test case') && !testCases.length)) {
                await designTests();
            } else if (userInput.toLowerCase().includes('implement') || userInput.toLowerCase().includes('code')) {
                await implementTests();
            } else if (userInput.toLowerCase().includes('verify') || userInput.toLowerCase().includes('run')) {
                await verifyTests();
            } else {
                // General chat (context-aware - handles test case refinement)
                addMessage('user', userInput);
                const result = await apiCall('/chat', 'POST', { message: userInput });
                updateMetricsFromResponse(result.metrics);
                
                // Check if backend updated test cases (refinement action)
                if (result.test_cases) {
                    setTestCases(result.test_cases);
                    addMessage('assistant', result.response, result.test_cases);
                } else {
                    addMessage('assistant', result.response);
                }
            }
        } catch (error) {
            addMessage('assistant', '❌ Error: ' + error.message);
        } finally {
            setLoading(false);
        }
    };

    // Reset agent
    const resetAgent = async () => {
        try {
            await apiCall('/reset', 'POST');
        } catch (error) {
            console.error('Reset error:', error);
        }
        
        setMessages([]);
        setPhase('idle');
        setPageStructure(null);
        setTestCases([]);
        setGeneratedCode('');
        setBrowserView('');
        setMetrics({ avgResponseTime: 0, tokensUsed: 0, iterationCount: 0 });
        addMessage('assistant', '🔄 Agent reset. Ready for a new session!');
    };

    // Download code
    const downloadCode = () => {
        const blob = new Blob([generatedCode], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'test_automation.py';
        a.click();
        URL.revokeObjectURL(url);
    };

    // Render backend status banner
    const renderStatusBanner = () => {
        if (backendStatus === 'connected') return null;
        
        const statusMessages = {
            'checking': { bg: 'bg-yellow-100', text: 'text-yellow-800', message: '🔄 Checking backend connection...' },
            'disconnected': { bg: 'bg-red-100', text: 'text-red-800', message: '❌ Backend not running. Start with: python main.py' },
            'api_missing': { bg: 'bg-orange-100', text: 'text-orange-800', message: '⚠️ API not running.' }
        };
        
        const status = statusMessages[backendStatus];
        return React.createElement('div', { 
            className: `${status.bg} ${status.text} px-4 py-2 text-center text-sm` 
        }, status.message);
    };

    // Render
    return React.createElement('div', { className: "flex h-screen bg-gray-50" },
        // Main Panel
        React.createElement('div', { className: "flex-1 flex flex-col" },
            renderStatusBanner(),
            React.createElement(window.Header, { onReset: resetAgent }),
            React.createElement(window.PhaseIndicator, { currentPhase: phase }),
            
            // Messages Area
            React.createElement('div', { className: "flex-1 overflow-y-auto p-4 space-y-4" },
                messages.length === 0 && React.createElement(window.WelcomeScreen),
                messages.map((msg, idx) => 
                    React.createElement(window.ChatMessage, { key: idx, message: msg })
                ),
                loading && React.createElement('div', { className: "flex justify-start" },
                    React.createElement('div', { className: "bg-white border rounded-lg p-4 shadow-sm" }, "Processing...")
                ),
                React.createElement('div', { ref: messagesEndRef })
            ),
            
            React.createElement(window.ChatInput, { 
                input, 
                setInput, 
                onSend: handleSend, 
                loading 
            })
        ),
        
        // Side Panel
        React.createElement('div', { className: "w-96 border-l bg-white flex flex-col" },
            React.createElement(window.BrowserView, { browserView }),
            React.createElement(window.MetricsPanel, { 
                metrics, 
                generatedCode, 
                onDownload: downloadCode 
            })
        )
    );
};

// Export for use in main
window.TestingAgent = TestingAgent;
