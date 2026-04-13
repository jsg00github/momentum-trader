import React from 'react';

/**
 * SkeletonCard — shimmer loading placeholder
 * Shows while data is being fetched. Uses the .skeleton CSS class from index.css.
 */
export function SkeletonCard({ lines = 3, className = '' }) {
    return (
        <div className={`glass-card p-4 ${className}`}>
            {Array.from({ length: lines }).map((_, i) => (
                <div
                    key={i}
                    className={`skeleton mb-3 ${i === 0 ? 'h-3' : 'h-6'}`}
                    style={{ width: `${60 + Math.random() * 35}%` }}
                />
            ))}
        </div>
    );
}

/**
 * SkeletonTable — loading placeholder for data tables
 */
export function SkeletonTable({ rows = 5, cols = 6, className = '' }) {
    return (
        <div className={`glass-card overflow-hidden ${className}`}>
            {/* Header */}
            <div className="flex gap-4 px-4 py-3 border-b border-white/5">
                {Array.from({ length: cols }).map((_, i) => (
                    <div key={i} className="skeleton h-3 flex-1" />
                ))}
            </div>
            {/* Rows */}
            {Array.from({ length: rows }).map((_, r) => (
                <div key={r} className="flex gap-4 px-4 py-3 border-b border-white/[0.02]">
                    {Array.from({ length: cols }).map((_, c) => (
                        <div
                            key={c}
                            className="skeleton h-4 flex-1"
                            style={{ width: `${50 + Math.random() * 40}%` }}
                        />
                    ))}
                </div>
            ))}
        </div>
    );
}

/**
 * SkeletonChart — loading placeholder for chart areas
 */
export function SkeletonChart({ height = 200, className = '' }) {
    return (
        <div className={`glass-card p-4 ${className}`}>
            <div className="skeleton h-3 w-32 mb-4" />
            <div className="skeleton" style={{ height: `${height}px` }} />
        </div>
    );
}

export default SkeletonCard;
