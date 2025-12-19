// Phase Indicator Component
const PhaseIndicator = ({ currentPhase }) => {
    const phases = ['idle', 'exploring', 'designing', 'implementing', 'verifying'];
    
    return React.createElement('div', { className: "bg-white border-b px-4 py-3" },
        React.createElement('div', { className: "flex items-center gap-4" },
            React.createElement('span', { className: "text-sm font-medium text-gray-600" }, "Phase:"),
            React.createElement('div', { className: "flex gap-2" },
                phases.map(p => 
                    React.createElement('span', {
                        key: p,
                        className: `px-3 py-1 rounded-full text-xs font-medium ${
                            currentPhase === p ? 'bg-blue-100 text-blue-700' :
                            currentPhase === p + 'ed' || (p === 'idle' && currentPhase === 'verified') 
                                ? 'bg-green-100 text-green-700' 
                                : 'bg-gray-100 text-gray-500'
                        }`
                    }, p.charAt(0).toUpperCase() + p.slice(1))
                )
            )
        )
    );
};

// Export for use in other modules
window.PhaseIndicator = PhaseIndicator;
