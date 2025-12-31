import { useState, useCallback } from 'react';
import { SessionBar } from './components/SessionBar';
import { ChatPanel } from './components/ChatPanel';
import { EventPanel } from './components/EventPanel';
import { useEventStream } from './hooks/useEventStream';
import { BedsheetEvent, ChatMessage, StreamState } from './types';

export default function App() {
  // Session state
  const [sessionId, setSessionId] = useState<string | null>(null);

  // Chat state
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [streamingContent, setStreamingContent] = useState('');

  // Event stream state
  const [events, setEvents] = useState<BedsheetEvent[]>([]);

  // Handle incoming events from SSE stream
  const handleEvent = useCallback((event: BedsheetEvent) => {
    setEvents(prev => [...prev, event]);

    switch (event.type) {
      case 'session':
        setSessionId(event.session_id);
        break;

      case 'text_token':
        setStreamingContent(prev => prev + event.token);
        break;

      case 'completion':
        // Add the completed assistant message
        setMessages(prev => [...prev, {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: event.response,
          timestamp: new Date(),
        }]);
        setStreamingContent('');
        break;

      case 'error':
        // Add error as assistant message
        setMessages(prev => [...prev, {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: `Error: ${event.error}`,
          timestamp: new Date(),
        }]);
        setStreamingContent('');
        break;

      case 'done':
        // Stream complete - if we have streaming content but no completion, add it
        if (streamingContent) {
          setMessages(prev => [...prev, {
            id: crypto.randomUUID(),
            role: 'assistant',
            content: streamingContent,
            timestamp: new Date(),
          }]);
          setStreamingContent('');
        }
        break;
    }
  }, [streamingContent]);

  const { sendMessage, state } = useEventStream(handleEvent);

  // Handle sending a message
  const handleSendMessage = useCallback((content: string) => {
    // Add user message to chat
    setMessages(prev => [...prev, {
      id: crypto.randomUUID(),
      role: 'user',
      content,
      timestamp: new Date(),
    }]);

    // Clear streaming content
    setStreamingContent('');

    // Send to backend
    sendMessage(content, sessionId || undefined);
  }, [sendMessage, sessionId]);

  // Handle new session
  const handleNewSession = useCallback(() => {
    setSessionId(null);
    setMessages([]);
    setEvents([]);
    setStreamingContent('');
  }, []);

  // Handle clearing events
  const handleClearEvents = useCallback(() => {
    setEvents([]);
  }, []);

  // Map hook state to StreamState type
  const streamState: StreamState = state === 'error' ? 'error' : state;
  const isStreaming = state === 'streaming' || state === 'connecting';

  return (
    <div className="h-screen flex flex-col bg-gray-950">
      {/* Top bar */}
      <SessionBar
        sessionId={sessionId}
        state={streamState}
        onNewSession={handleNewSession}
      />

      {/* Main content - side by side panels */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left: Chat panel */}
        <div className="w-1/2 border-r border-gray-700">
          <ChatPanel
            messages={messages}
            onSendMessage={handleSendMessage}
            isStreaming={isStreaming}
            streamingContent={streamingContent}
          />
        </div>

        {/* Right: Event panel */}
        <div className="w-1/2">
          <EventPanel
            events={events}
            onClear={handleClearEvents}
          />
        </div>
      </div>
    </div>
  );
}
