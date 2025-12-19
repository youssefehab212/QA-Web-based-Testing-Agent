// Browser View Component
const BrowserView = ({ browserView }) => {
    const { Camera } = window.Icons;
    
    return React.createElement('div', { className: "flex-1 border-b" },
        React.createElement('div', { className: "bg-gray-100 px-4 py-3 border-b" },
            React.createElement('h3', { className: "font-medium flex items-center gap-2" },
                React.createElement(Camera),
                "Browser View"
            )
        ),
        React.createElement('div', { className: "p-4" },
            browserView 
                ? React.createElement('div', { 
                    className: "bg-gray-900 text-green-400 p-4 rounded font-mono text-xs whitespace-pre-wrap" 
                }, browserView)
                : React.createElement('div', { className: "text-center text-gray-400 py-8" },
                    React.createElement(Camera),
                    React.createElement('p', { className: "text-sm" }, "No page loaded")
                )
        )
    );
};

// Export for use in other modules
window.BrowserView = BrowserView;
