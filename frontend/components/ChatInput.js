// Chat Input Component
const ChatInput = ({ input, setInput, onSend, loading }) => {
    const { Play } = window.Icons;
    
    const handleKeyPress = (e) => {
        if (e.key === 'Enter') {
            onSend();
        }
    };
    
    return React.createElement('div', { className: "border-t bg-white p-4" },
        React.createElement('div', { className: "flex gap-2" },
            React.createElement('input', {
                type: "text",
                value: input,
                onChange: (e) => setInput(e.target.value),
                onKeyPress: handleKeyPress,
                placeholder: "Enter URL or ask about testing...",
                className: "flex-1 px-4 py-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            }),
            React.createElement('button', {
                onClick: onSend,
                disabled: loading,
                className: "px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition"
            },
                React.createElement(Play)
            )
        )
    );
};

// Export for use in other modules
window.ChatInput = ChatInput;
