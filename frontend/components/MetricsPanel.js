// Metrics Panel Component
const MetricsPanel = ({ metrics, generatedCode, onDownload }) => {
    const { Clock, Zap, FileText, CheckCircle, Download } = window.Icons;
    
    return React.createElement('div', { className: "p-4 space-y-4" },
        React.createElement('h3', { className: "font-medium flex items-center gap-2" },
            React.createElement(Zap),
            "Agent Metrics"
        ),
        
        React.createElement('div', { className: "space-y-3" },
            // Average Response Time
            React.createElement('div', { className: "bg-blue-50 p-3 rounded-lg" },
                React.createElement('div', { className: "flex items-center justify-between mb-1" },
                    React.createElement('span', { className: "text-xs font-medium text-blue-900" }, "Avg Response Time"),
                    React.createElement(Clock)
                ),
                React.createElement('p', { className: "text-2xl font-bold text-blue-600" },
                    metrics.avgResponseTime > 0 ? `${metrics.avgResponseTime.toFixed(2)}s` : '-'
                )
            ),
            
            // Tokens Consumed
            React.createElement('div', { className: "bg-purple-50 p-3 rounded-lg" },
                React.createElement('div', { className: "flex items-center justify-between mb-1" },
                    React.createElement('span', { className: "text-xs font-medium text-purple-900" }, "Tokens Consumed"),
                    React.createElement(FileText)
                ),
                React.createElement('p', { className: "text-2xl font-bold text-purple-600" }, 
                    metrics.tokensUsed.toLocaleString()
                )
            ),
            
            // Iterations
            React.createElement('div', { className: "bg-green-50 p-3 rounded-lg" },
                React.createElement('div', { className: "flex items-center justify-between mb-1" },
                    React.createElement('span', { className: "text-xs font-medium text-green-900" }, "Iterations"),
                    React.createElement(CheckCircle)
                ),
                React.createElement('p', { className: "text-2xl font-bold text-green-600" }, 
                    metrics.iterationCount
                )
            )
        ),
        
        // Download Button
        generatedCode && React.createElement('button', {
            onClick: onDownload,
            className: "w-full flex items-center justify-center gap-2 bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700"
        },
            React.createElement(Download),
            "Download Code"
        )
    );
};

// Export for use in other modules
window.MetricsPanel = MetricsPanel;
