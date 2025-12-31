import React, { useState } from 'react';

interface SessionBarProps {
  sessionId: string | null;
  state: 'idle' | 'connecting' | 'streaming' | 'error';
  onNewSession: () => void;
}

export const SessionBar: React.FC<SessionBarProps> = ({
  sessionId,
  state,
  onNewSession,
}) => {
  const [copied, setCopied] = useState(false);

  const handleCopySessionId = async () => {
    if (sessionId) {
      try {
        await navigator.clipboard.writeText(sessionId);
        setCopied(true);
        // Reset the copied state after 2 seconds
        setTimeout(() => setCopied(false), 2000);
      } catch (err) {
        console.error('Failed to copy session ID:', err);
      }
    }
  };

  const getStateColor = (s: string) => {
    switch (s) {
      case 'idle':
        return 'bg-gray-500';
      case 'connecting':
        return 'bg-yellow-500 animate-pulse';
      case 'streaming':
        return 'bg-green-500 animate-pulse';
      case 'error':
        return 'bg-red-500';
      default:
        return 'bg-gray-500';
    }
  };

  const getStateLabel = (s: string) => {
    switch (s) {
      case 'idle':
        return 'Idle';
      case 'connecting':
        return 'Connecting';
      case 'streaming':
        return 'Streaming';
      case 'error':
        return 'Error';
      default:
        return 'Unknown';
    }
  };

  const truncateSessionId = (id: string, length: number = 12) => {
    if (id.length <= length) return id;
    return `${id.substring(0, length / 2)}...${id.substring(
      id.length - length / 2
    )}`;
  };

  return (
    <div className="h-12 bg-gray-900 border-b border-gray-700 flex items-center justify-between px-4 gap-4">
      {/* Left: Title */}
      <div className="flex-shrink-0">
        <h1 className="text-sm font-semibold text-white">Bedsheet Debug UI</h1>
      </div>

      {/* Center: Session ID and Connection State */}
      <div className="flex-1 flex items-center justify-center gap-3 min-w-0">
        {/* Connection State Indicator */}
        <div className="flex items-center gap-2 flex-shrink-0">
          <div
            className={`w-3 h-3 rounded-full ${getStateColor(state)}`}
            title={getStateLabel(state)}
          />
          <span className="text-xs text-gray-400">{getStateLabel(state)}</span>
        </div>

        {/* Session ID */}
        {sessionId ? (
          <button
            onClick={handleCopySessionId}
            className="text-xs text-gray-400 font-mono px-2 py-1 rounded hover:bg-gray-800 transition-colors cursor-pointer hover:text-gray-300 flex-shrink-0"
            title="Click to copy session ID"
          >
            {truncateSessionId(sessionId)}
            {copied && <span className="ml-1 text-green-400">✓</span>}
          </button>
        ) : (
          <span className="text-xs text-gray-500 font-mono">No session</span>
        )}
      </div>

      {/* Right: New Session Button */}
      <div className="flex-shrink-0">
        <button
          onClick={onNewSession}
          className="px-3 py-1.5 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 transition-colors"
        >
          New Session
        </button>
      </div>
    </div>
  );
};
