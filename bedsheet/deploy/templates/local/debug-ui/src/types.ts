/**
 * Bedsheet Debug UI Type Definitions
 *
 * Comprehensive TypeScript types for all events that stream from the Bedsheet agent
 * via Server-Sent Events (SSE). These types model the full event lifecycle from
 * session initialization through completion.
 */

/**
 * All possible event types that can be emitted from the Bedsheet SSE stream
 */
export type EventType =
  | 'session'
  | 'thinking'
  | 'text_token'
  | 'tool_call'
  | 'tool_result'
  | 'completion'
  | 'error'
  | 'routing'
  | 'delegation'
  | 'collaborator_start'
  | 'collaborator'
  | 'collaborator_complete'
  | 'done';

/**
 * Session initialization event
 * Marks the start of a new agent session
 */
export interface SessionEvent {
  type: 'session';
  session_id: string;
}

/**
 * Internal reasoning/thinking event
 * Emitted when the agent is thinking through a problem
 */
export interface ThinkingEvent {
  type: 'thinking';
  content: string;
}

/**
 * Individual text token from the LLM response
 * Emitted incrementally as the model generates tokens
 */
export interface TextTokenEvent {
  type: 'text_token';
  token: string;
}

/**
 * Tool invocation event
 * Emitted when the agent decides to call a tool
 */
export interface ToolCallEvent {
  type: 'tool_call';
  tool_name: string;
  tool_input: Record<string, any>;
  call_id: string;
}

/**
 * Tool result event
 * Emitted with the result of a tool call, or error if it failed
 */
export interface ToolResultEvent {
  type: 'tool_result';
  call_id: string;
  result: any;
  error?: string;
}

/**
 * Completion event
 * Emitted when the agent completes its response
 */
export interface CompletionEvent {
  type: 'completion';
  response: string;
}

/**
 * Error event
 * Emitted when an error occurs during agent execution
 */
export interface ErrorEvent {
  type: 'error';
  error: string;
  recoverable: boolean;
}

/**
 * Routing event (for multi-agent systems)
 * Emitted when the supervisor routes a task to a specific agent
 */
export interface RoutingEvent {
  type: 'routing';
  agent_name: string;
  task: string;
}

/**
 * Delegation event (for multi-agent systems)
 * Emitted when multiple agents are delegated parallel tasks
 */
export interface DelegationEvent {
  type: 'delegation';
  delegations: Array<{
    agent: string;
    task: string;
  }>;
}

/**
 * Collaborator start event (for multi-agent systems)
 * Emitted when a collaborator agent begins processing
 */
export interface CollaboratorStartEvent {
  type: 'collaborator_start';
  agent_name: string;
  task: string;
}

/**
 * Collaborator update event (for multi-agent systems)
 * Emitted as a collaborator agent produces output
 */
export interface CollaboratorEvent {
  type: 'collaborator';
  agent_name: string;
}

/**
 * Collaborator completion event (for multi-agent systems)
 * Emitted when a collaborator agent completes its task
 */
export interface CollaboratorCompleteEvent {
  type: 'collaborator_complete';
  agent_name: string;
  response: string;
}

/**
 * Stream completion event
 * Emitted when the entire stream has ended
 */
export interface DoneEvent {
  type: 'done';
}

/**
 * Union type representing any possible Bedsheet event
 */
export type BedsheetEvent =
  | SessionEvent
  | ThinkingEvent
  | TextTokenEvent
  | ToolCallEvent
  | ToolResultEvent
  | CompletionEvent
  | ErrorEvent
  | RoutingEvent
  | DelegationEvent
  | CollaboratorStartEvent
  | CollaboratorEvent
  | CollaboratorCompleteEvent
  | DoneEvent;

/**
 * Chat message in the conversation history
 * Represents either a user message or an assistant response
 */
export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

/**
 * Stream connection state
 * Tracks the current status of the SSE connection
 */
export type StreamState = 'idle' | 'connecting' | 'streaming' | 'error';

/**
 * Stream connection status and metadata
 */
export interface StreamStatus {
  state: StreamState;
  session_id?: string;
  error_message?: string;
  connected_at?: Date;
}
