import React, { useRef, useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';

interface ChatPanelProps {
  messages: Array<{
    id: string;
    role: 'user' | 'assistant';
    content: string;
    timestamp: Date;
  }>;
  onSendMessage: (message: string) => void;
  isStreaming: boolean;
  streamingContent: string;
}

export const ChatPanel: React.FC<ChatPanelProps> = ({
  messages,
  onSendMessage,
  isStreaming,
  streamingContent,
}) => {
  const [inputValue, setInputValue] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingContent, isStreaming]);

  const handleSendMessage = () => {
    if (inputValue.trim() && !isStreaming) {
      onSendMessage(inputValue.trim());
      setInputValue('');
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !isStreaming) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const formatTimestamp = (date: Date) => {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div className="flex flex-col h-full bg-gray-800">
      {/* Messages Container */}
      <div
        ref={messagesContainerRef}
        className="flex-1 overflow-y-auto p-4 space-y-4"
      >
        {messages.length === 0 && !isStreaming && (
          <div className="flex items-center justify-center h-full text-gray-400">
            <p className="text-center">
              Start a conversation with the agent. Send a message to begin.
            </p>
          </div>
        )}

        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex ${
              message.role === 'user' ? 'justify-end' : 'justify-start'
            }`}
          >
            <div
              className={`max-w-xs lg:max-w-md xl:max-w-2xl px-4 py-2 rounded-lg ${
                message.role === 'user'
                  ? 'bg-blue-600 text-white rounded-br-none'
                  : 'bg-gray-700 text-gray-100 rounded-bl-none'
              }`}
            >
              <div className="prose prose-sm prose-invert max-w-none break-words">
                <ReactMarkdown
                  components={{
                    h1: ({children}) => <h1 className="text-lg font-bold mt-2 mb-1">{children}</h1>,
                    h2: ({children}) => <h2 className="text-base font-bold mt-2 mb-1">{children}</h2>,
                    h3: ({children}) => <h3 className="text-sm font-bold mt-1 mb-1">{children}</h3>,
                    p: ({children}) => <p className="mb-2 last:mb-0">{children}</p>,
                    ul: ({children}) => <ul className="list-disc list-inside mb-2 space-y-1">{children}</ul>,
                    ol: ({children}) => <ol className="list-decimal list-inside mb-2 space-y-1">{children}</ol>,
                    li: ({children}) => <li className="text-sm">{children}</li>,
                    strong: ({children}) => <strong className="font-bold">{children}</strong>,
                    em: ({children}) => <em className="italic">{children}</em>,
                    code: ({children}) => <code className="bg-gray-800 px-1 py-0.5 rounded text-xs">{children}</code>,
                    pre: ({children}) => <pre className="bg-gray-800 p-2 rounded my-2 overflow-x-auto text-xs">{children}</pre>,
                  }}
                >
                  {message.content}
                </ReactMarkdown>
              </div>
              <p
                className={`text-xs mt-1 ${
                  message.role === 'user'
                    ? 'text-blue-200'
                    : 'text-gray-400'
                }`}
              >
                {formatTimestamp(message.timestamp)}
              </p>
            </div>
          </div>
        ))}

        {/* Streaming Content (Typing Indicator) */}
        {isStreaming && streamingContent && (
          <div className="flex justify-start">
            <div className="max-w-xs lg:max-w-md xl:max-w-2xl px-4 py-2 rounded-lg bg-gray-700 text-gray-100 rounded-bl-none">
              <div className="prose prose-sm prose-invert max-w-none break-words">
                <ReactMarkdown
                  components={{
                    h1: ({children}) => <h1 className="text-lg font-bold mt-2 mb-1">{children}</h1>,
                    h2: ({children}) => <h2 className="text-base font-bold mt-2 mb-1">{children}</h2>,
                    h3: ({children}) => <h3 className="text-sm font-bold mt-1 mb-1">{children}</h3>,
                    p: ({children}) => <p className="mb-2 last:mb-0">{children}</p>,
                    ul: ({children}) => <ul className="list-disc list-inside mb-2 space-y-1">{children}</ul>,
                    ol: ({children}) => <ol className="list-decimal list-inside mb-2 space-y-1">{children}</ol>,
                    li: ({children}) => <li className="text-sm">{children}</li>,
                    strong: ({children}) => <strong className="font-bold">{children}</strong>,
                    em: ({children}) => <em className="italic">{children}</em>,
                    code: ({children}) => <code className="bg-gray-800 px-1 py-0.5 rounded text-xs">{children}</code>,
                    pre: ({children}) => <pre className="bg-gray-800 p-2 rounded my-2 overflow-x-auto text-xs">{children}</pre>,
                  }}
                >
                  {streamingContent}
                </ReactMarkdown>
              </div>
              <div className="flex items-center mt-2 space-x-1">
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-pulse"></div>
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-pulse" style={{ animationDelay: '0.1s' }}></div>
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-pulse" style={{ animationDelay: '0.2s' }}></div>
              </div>
            </div>
          </div>
        )}

        {/* Empty Streaming State */}
        {isStreaming && !streamingContent && (
          <div className="flex justify-start">
            <div className="max-w-xs lg:max-w-md px-4 py-2 rounded-lg bg-gray-700 text-gray-100 rounded-bl-none">
              <div className="flex items-center space-x-2">
                <span className="text-sm text-gray-400">Agent is thinking</span>
                <div className="flex items-center space-x-1">
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-pulse"></div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-pulse" style={{ animationDelay: '0.1s' }}></div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-pulse" style={{ animationDelay: '0.2s' }}></div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Auto-scroll anchor */}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="border-t border-gray-700 p-4 bg-gray-800">
        <div className="flex gap-2">
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Type a message..."
            disabled={isStreaming}
            className="flex-1 px-4 py-2 rounded-lg bg-gray-700 text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-sm"
          />
          <button
            onClick={handleSendMessage}
            disabled={isStreaming || !inputValue.trim()}
            className="px-4 py-2 rounded-lg bg-blue-600 text-white font-medium hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed transition-colors text-sm"
          >
            Send
          </button>
        </div>
        {isStreaming && (
          <p className="text-xs text-gray-400 mt-2">
            Waiting for agent response...
          </p>
        )}
      </div>
    </div>
  );
};
