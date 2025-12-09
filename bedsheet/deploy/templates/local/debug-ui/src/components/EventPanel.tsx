import React, { useRef, useEffect } from 'react';
import { BedsheetEvent } from '../types';
import { EventItem } from './EventItem';

interface EventPanelProps {
  events: BedsheetEvent[];
  onClear: () => void;
}

export const EventPanel: React.FC<EventPanelProps> = ({
  events,
  onClear,
}) => {
  const eventsEndRef = useRef<HTMLDivElement>(null);
  const eventsContainerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when events change
  useEffect(() => {
    eventsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [events]);

  return (
    <div className="flex flex-col h-full bg-gray-900">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-700 bg-gray-850">
        <h2 className="text-lg font-semibold text-white">
          Events ({events.length})
        </h2>
        <button
          onClick={onClear}
          disabled={events.length === 0}
          className="px-3 py-1 rounded-md text-sm font-medium bg-gray-700 text-gray-200 hover:bg-gray-600 disabled:bg-gray-800 disabled:text-gray-500 disabled:cursor-not-allowed transition-colors"
        >
          Clear
        </button>
      </div>

      {/* Events Container */}
      <div
        ref={eventsContainerRef}
        className="flex-1 overflow-y-auto p-4 space-y-2"
      >
        {events.length === 0 && (
          <div className="flex items-center justify-center h-full">
            <p className="text-gray-400 text-center text-sm">
              No events yet. Send a message to start.
            </p>
          </div>
        )}

        {events.map((event, index) => (
          <EventItem key={index} event={event} index={index} />
        ))}

        {/* Auto-scroll anchor */}
        <div ref={eventsEndRef} />
      </div>
    </div>
  );
};
