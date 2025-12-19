// Header Component
const Header = ({ onReset }) => {
    const { RefreshCw } = window.Icons;
    
    return React.createElement('div', { 
        className: "bg-gradient-to-r from-blue-600 to-purple-600 text-white p-4 shadow-lg" 
    },
        React.createElement('div', { className: "flex items-center justify-between" },
            React.createElement('div', null,
                React.createElement('h1', { className: "text-2xl font-bold" }, "QA Testing Agent"),
                React.createElement('p', { className: "text-sm opacity-90" }, "Human-in-the-Loop Test Automation")
            ),
            React.createElement('button', {
                onClick: onReset,
                className: "flex items-center gap-2 bg-white/20 hover:bg-white/30 px-4 py-2 rounded-lg transition"
            },
                React.createElement(RefreshCw),
                "Reset"
            )
        )
    );
};

// Export for use in other modules
window.Header = Header;
