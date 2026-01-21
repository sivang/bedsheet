import { useState, useCallback, useRef } from 'react';
import { BedsheetEvent, StreamState } from '../types';

/**
 * Hook for streaming Bedsheet agent events via Server-Sent Events (SSE)
 *
 * Manages SSE connection lifecycle, parses events, and provides control
 * over the stream connection.
 *
 * @param onEvent Callback fired for each event received from the stream
 * @returns Object with sendMessage function, current state, and abort function
 */
export function useEventStream(onEvent: (event: BedsheetEvent) => void) {
  const [state, setState] = useState<StreamState>('idle');
  const [error, setError] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const readerRef = useRef<ReadableStreamDefaultReader<Uint8Array> | null>(null);

  /**
   * Parses a single SSE "data:" line into a BedsheetEvent
   * Each line should be: "data: {json}"
   */
  const parseSSELine = (line: string): BedsheetEvent | null => {
    const trimmed = line.trim();
    if (!trimmed.startsWith('data:')) {
      return null;
    }

    const jsonString = trimmed.substring(5).trim();
    if (!jsonString) {
      return null;
    }

    try {
      return JSON.parse(jsonString) as BedsheetEvent;
    } catch (err) {
      console.error('Failed to parse SSE event:', jsonString, err);
      return null;
    }
  };

  /**
   * Reads from the response stream, accumulating incomplete lines
   * and calling onEvent for complete lines
   */
  const processStream = async (reader: ReadableStreamDefaultReader<Uint8Array>) => {
    let buffer = '';
    const decoder = new TextDecoder();

    try {
      while (true) {
        const { done, value } = await reader.read();

        if (done) {
          // Process any remaining content in buffer
          if (buffer.trim()) {
            const event = parseSSELine(buffer);
            if (event) {
              onEvent(event);
            }
          }
          break;
        }

        // Decode chunk and append to buffer
        buffer += decoder.decode(value, { stream: true });

        // Process complete lines (separated by \n\n in SSE format)
        const lines = buffer.split('\n\n');

        // Keep the last incomplete line in buffer
        buffer = lines[lines.length - 1] || '';

        // Process all complete lines
        for (let i = 0; i < lines.length - 1; i++) {
          const line = lines[i];
          if (line.trim()) {
            const event = parseSSELine(line);
            if (event) {
              onEvent(event);
            }
          }
        }
      }
    } catch (err) {
      if (err instanceof Error && err.name !== 'AbortError') {
        throw err;
      }
    }
  };

  /**
   * Sends a message to the /invoke/stream endpoint and streams events
   *
   * @param message The message to send to the agent
   * @param sessionId Optional session ID to continue an existing session
   */
  const sendMessage = useCallback(
    async (message: string, sessionId?: string) => {
      // Clean up any existing connection
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }

      // Create new abort controller for this request
      const abortController = new AbortController();
      abortControllerRef.current = abortController;

      setState('connecting');
      setError(null);

      try {
        // Send POST request to /invoke/stream
        const response = await fetch('/invoke/stream', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            message,
            ...(sessionId && { session_id: sessionId }),
          }),
          signal: abortController.signal,
        });

        if (!response.ok) {
          const errorText = await response.text();
          throw new Error(
            `HTTP ${response.status}: ${errorText || response.statusText}`
          );
        }

        // Check for proper SSE content type
        const contentType = response.headers.get('content-type');
        if (!contentType?.includes('text/event-stream')) {
          console.warn('Expected text/event-stream, got:', contentType);
        }

        if (!response.body) {
          throw new Error('Response body is null');
        }

        setState('streaming');

        // Get reader from response body
        const reader = response.body.getReader();
        readerRef.current = reader;

        // Process the stream
        await processStream(reader);

        // Emit done event when stream completes
        onEvent({ type: 'done' });

        setState('idle');
      } catch (err) {
        // Don't set error state for abort errors
        if (err instanceof Error && err.name === 'AbortError') {
          setState('idle');
          return;
        }

        const errorMessage =
          err instanceof Error ? err.message : 'Unknown error occurred';
        setError(errorMessage);
        setState('error');

        console.error('Stream error:', err);
      } finally {
        readerRef.current = null;
      }
    },
    [onEvent]
  );

  /**
   * Aborts the current streaming connection
   */
  const abort = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    if (readerRef.current) {
      readerRef.current.cancel();
      readerRef.current = null;
    }
    setState('idle');
    setError(null);
  }, []);

  return {
    sendMessage,
    state,
    error,
    abort,
  };
}
