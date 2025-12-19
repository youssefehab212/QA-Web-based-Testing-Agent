// Chat Message Component
const ChatMessage = ({ message }) => {
    const { useState } = React;
    const { role, content, data } = message;
    const [showAllElements, setShowAllElements] = useState(false);
    
    // Determine how many elements to show
    const elementsToShow = data?.elements 
        ? (showAllElements ? data.elements : data.elements.slice(0, 5))
        : [];
    const hasMoreElements = data?.elements?.length > 5;
    
    return React.createElement('div', { 
        className: `flex ${role === 'user' ? 'justify-end' : 'justify-start'}` 
    },
        React.createElement('div', { 
            className: `max-w-3xl rounded-lg p-4 ${role === 'user' ? 'bg-blue-600 text-white' : 'bg-white border shadow-sm'}` 
        },
            React.createElement('div', { className: "whitespace-pre-wrap" }, content),
            
            // Page Elements Display
            data && data.elements && React.createElement('div', { 
                className: "mt-3 p-3 bg-gray-50 rounded text-sm" 
            },
                React.createElement('p', { className: "font-medium mb-2" }, 
                    `Page Elements (${data.elements.length} total):`
                ),
                React.createElement('div', { className: "space-y-1" },
                    elementsToShow.map((el, i) => 
                        React.createElement('div', { key: i, className: "text-xs" },
                            React.createElement('span', { className: "font-mono bg-gray-200 px-1 rounded" }, el.locator),
                            ' - ', el.description
                        )
                    )
                ),
                // Show more/less button
                hasMoreElements && React.createElement('button', {
                    className: "mt-2 text-xs text-blue-600 hover:text-blue-800 font-medium cursor-pointer",
                    onClick: () => setShowAllElements(!showAllElements)
                }, 
                    showAllElements 
                        ? `▲ Show less` 
                        : `▼ Show ${data.elements.length - 5} more elements`
                )
            ),
            
            // Test Cases Display
            data && Array.isArray(data) && React.createElement('div', { className: "mt-3 space-y-2" },
                data.map((tc, i) => 
                    React.createElement('div', { key: i, className: "p-2 bg-gray-50 rounded text-sm" },
                        React.createElement('div', { className: "flex items-center gap-2" },
                            React.createElement('span', { className: "font-mono text-xs bg-blue-100 px-2 py-0.5 rounded" }, tc.id),
                            React.createElement('span', { className: "font-medium" }, tc.title)
                        )
                    )
                )
            )
        )
    );
};

// Export for use in other modules
window.ChatMessage = ChatMessage;
