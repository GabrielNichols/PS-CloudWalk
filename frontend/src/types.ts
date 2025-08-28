export interface Message {
  id: string;
  content: string;
  role: 'user' | 'assistant';
  timestamp: Date;
  sources?: Array<{
    url: string;
    title?: string;
  }>;
  metadata?: {
    agent?: string;
    confidence?: number;
    latency_ms?: number;
    tokens?: number;
    mode?: string;
  };
  isStreaming?: boolean;
}

export interface Session {
  id: string;
  messages: Message[];
  createdAt: Date;
  updatedAt: Date;
}

export interface ChatState {
  messages: Message[];
  isLoading: boolean;
  currentSessionId: string | null;
}
