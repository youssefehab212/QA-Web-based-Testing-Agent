// Welcome Screen Component
const WelcomeScreen = () => {
    const { Eye } = window.Icons;
    
    return React.createElement('div', { className: "text-center text-gray-500 mt-8" },
        React.createElement(Eye),
        React.createElement('h3', { className: "text-lg font-medium mb-2" }, "Welcome to QA Testing Agent"),
        React.createElement('p', { className: "text-sm" }, "Start by pasting a URL to explore")
    );
};

// Export for use in other modules
window.WelcomeScreen = WelcomeScreen;
