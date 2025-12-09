import React, { useState } from 'react';
import { BedsheetEvent } from '../types';

interface EventItemProps {
  event: BedsheetEvent;
  index: number;
}

/**
 * Helper to truncate strings for display
 */
const truncate = (text: string, maxLength: number = 50): string => {
  if (text.length <= maxLength) return text;
  return text.substring(0, maxLength) + '...';
};

/**
 * Helper to get the badge color and label for an event type
 */
const getBadgeStyles = (eventType: string): { bg: string; text: string; label: string } => {
  switch (eventType) {
    case 'tool_call':
      return { bg: 'bg-blue-900', text: 'text-blue-200', label: '🔧' };
    case 'tool_result':
      return { bg: 'bg-green-900', text: 'text-green-200', label: '✓' };
    case 'text_token':
      return { bg: 'bg-slate-700', text: 'text-slate-300', label: '📝' };
    case 'completion':
      return { bg: 'bg-purple-900', text: 'text-purple-200', label: '✔️' };
    case 'error':
      return { bg: 'bg-red-900', text: 'text-red-200', label: '✗' };
    case 'thinking':
      return { bg: 'bg-yellow-900', text: 'text-yellow-200', label: '💭' };
    case 'routing':
    case 'delegation':
    case 'collaborator_start':
    case 'collaborator':
    case 'collaborator_complete':
      return { bg: 'bg-orange-900', text: 'text-orange-200', label: '→' };
    case 'session':
    case 'done':
      return { bg: 'bg-slate-700', text: 'text-slate-300', label: '●' };
    default:
      return { bg: 'bg-slate-700', text: 'text-slate-300', label: '◆' };
  }
};

/**
 * Helper to generate a summary for the collapsed view
 */
const getSummary = (event: BedsheetEvent): string => {
  switch (event.type) {
    case 'tool_call':
      return `→ ${event.tool_name}`;
    case 'tool_result':
      if (event.error) {
        return `← Error: ${truncate(event.error)}`;
      }
      const resultStr = typeof event.result === 'string'
        ? event.result
        : JSON.stringify(event.result);
      return `← ${truncate(resultStr)}`;
    case 'text_token':
      return event.token;
    case 'completion':
      return `✓ ${truncate(event.response)}`;
    case 'error':
      return `✗ ${truncate(event.error)}`;
    case 'thinking':
      return `💭 ${truncate(event.content)}`;
    case 'routing':
      return `→ Route to ${event.agent_name}: ${truncate(event.task)}`;
    case 'delegation':
      const agentCount = event.delegations.length;
      return `→ Delegate to ${agentCount} agent${agentCount > 1 ? 's' : ''}`;
    case 'collaborator_start':
      return `→ ${event.agent_name} starting: ${truncate(event.task)}`;
    case 'collaborator_complete':
      return `← ${event.agent_name} done: ${truncate(event.response)}`;
    case 'collaborator':
      return `◆ Collaborator update from ${event.agent_name}`;
    case 'session':
      return `● Session ${event.session_id.substring(0, 8)}...`;
    case 'done':
      return '● Stream complete';
    default:
      return 'Event';
  }
};

/**
 * Helper to determine if an event can be expanded
 * Text tokens are always inline and can't be expanded
 */
const canExpand = (event: BedsheetEvent): boolean => {
  return event.type !== 'text_token';
};

/**
 * EventItem component
 * Renders a single event with collapse/expand functionality
 */
export const EventItem: React.FC<EventItemProps> = ({ event, index }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const badge = getBadgeStyles(event.type);
  const summary = getSummary(event);
  const expandable = canExpand(event);

  // Special handling for text_token - render inline without expand
  if (event.type === 'text_token') {
    return (
      <div className="inline-block">
        <span className={`text-xs font-mono ${badge.text}`}>
          {event.token}
        </span>
      </div>
    );
  }

  return (
    <div className={`flex items-start gap-2 p-2 rounded border-l-2 border-l-slate-600 ${expandable ? 'cursor-pointer hover:bg-slate-800/50' : ''}`}>
      {/* Badge */}
      <div
        className={`flex-shrink-0 px-2 py-1 rounded text-xs font-semibold whitespace-nowrap ${badge.bg} ${badge.text}`}
        onClick={() => expandable && setIsExpanded(!isExpanded)}
      >
        {badge.label}
      </div>

      {/* Content Area */}
      <div
        className="flex-1 min-w-0"
        onClick={() => expandable && setIsExpanded(!isExpanded)}
      >
        {!isExpanded ? (
          // Collapsed view
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs truncate text-slate-300">
              {summary}
            </span>
            {expandable && (
              <span className="text-xs text-slate-500 flex-shrink-0">
                {isExpanded ? '▾' : '▸'}
              </span>
            )}
          </div>
        ) : (
          // Expanded view
          <div className="space-y-1">
            <div className="flex items-center justify-between gap-2 mb-2">
              <span className="text-xs font-semibold text-slate-400">
                {event.type}
              </span>
              <button
                onClick={() => setIsExpanded(false)}
                className="text-xs text-slate-500 hover:text-slate-300 transition-colors"
              >
                ▾
              </button>
            </div>
            <pre className="text-xs bg-slate-950 p-2 rounded overflow-x-auto border border-slate-700 max-h-64 overflow-y-auto text-slate-200 font-mono whitespace-pre-wrap break-words">
              {JSON.stringify(event, null, 2)}
            </pre>
          </div>
        )}
      </div>

      {/* Index indicator (right side, subtle) */}
      <div className="flex-shrink-0 text-xs text-slate-600 opacity-50">
        #{index}
      </div>
    </div>
  );
};
