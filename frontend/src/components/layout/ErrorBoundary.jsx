import React from 'react';

/**
 * ErrorBoundary — catches rendering errors in child components
 * and displays a fallback UI instead of crashing the whole app.
 */
class ErrorBoundary extends React.Component {
    constructor(props) {
        super(props);
        this.state = { hasError: false, error: null, errorInfo: null };
    }

    static getDerivedStateFromError(error) {
        return { hasError: true, error };
    }

    componentDidCatch(error, errorInfo) {
        this.setState({ errorInfo });
        console.error('[ErrorBoundary]', error, errorInfo);
    }

    render() {
        if (this.state.hasError) {
            return (
                <div className="flex items-center justify-center min-h-[200px] p-8">
                    <div className="bg-red-900/20 border border-red-700/50 rounded-2xl p-8 max-w-lg w-full text-center">
                        <div className="text-4xl mb-4">💥</div>
                        <h2 className="text-xl font-bold text-red-400 mb-2">
                            {this.props.fallbackTitle || 'Something went wrong'}
                        </h2>
                        <p className="text-sm text-slate-400 mb-4">
                            This section encountered an error. The rest of the app still works.
                        </p>
                        <details className="text-left text-xs text-slate-500 bg-black/30 p-3 rounded-lg mb-4">
                            <summary className="cursor-pointer text-slate-400 font-bold">Error Details</summary>
                            <pre className="mt-2 overflow-auto max-h-32 text-red-300">
                                {this.state.error?.toString()}
                            </pre>
                        </details>
                        <button
                            onClick={() => this.setState({ hasError: false, error: null, errorInfo: null })}
                            className="px-6 py-2 bg-red-600 hover:bg-red-500 text-white font-bold rounded-lg transition"
                        >
                            🔄 Try Again
                        </button>
                    </div>
                </div>
            );
        }

        return this.props.children;
    }
}

export default ErrorBoundary;
