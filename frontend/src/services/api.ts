import axios from 'axios';
import { Message } from '../types';

// Resolve API base URL:
// - Use REACT_APP_API_URL if provided
// - On CRA dev server (:3000), default to http://localhost:8000
// - In production (Vercel), use relative paths ('') so vercel.json rewrites route to Python API
function resolveApiBase(): string {
  const envBase = process.env.REACT_APP_API_URL;
  if (envBase && typeof envBase === 'string') return envBase.replace(/\/+$/, '');
  if (typeof window !== 'undefined') {
    const isDev = process.env.NODE_ENV !== 'production';
    if (isDev && window.location.port === '3000') {
      return 'http://localhost:8000';
    }
  }
  return '';
}

const API_BASE_URL = resolveApiBase();
const apiPath = (path: string) => `${API_BASE_URL}${path}`;

interface ApiResponse {
  ok: boolean;
  agent: string;
  answer: string;
  grounding?: {
    mode: string;
    sources?: Array<{ url: string; title?: string }>;
    confidence: number;
  };
  meta?: any;
}

type StreamEvent =
  | { type: 'chunk'; content: string; is_complete?: boolean }
  | {
      type: 'complete';
      answer: string;
      agent?: string;
      grounding?: {
        mode?: string;
        sources?: Array<{ url: string; title?: string }>;
        confidence?: number;
      };
      meta?: any;
    }
  | { type: 'error'; error: string };

class ChatApiService {
  private getClientIP(): string {
    // Frontend cannot reliably know IP; backend should infer from request if needed
    return 'local';
  }

  async sendMessage(message: string, userId?: string): Promise<Message> {
    const clientIP = this.getClientIP();
    const sessionId = userId || `session_${clientIP}_${Date.now()}`;

    const response = await axios.post<ApiResponse>(apiPath('/api/v1/message'), {
      message,
      user_id: sessionId,
      locale: 'pt-BR',
    });
    const data = response.data;
    if (!data.ok) throw new Error('API returned error status');

    return {
      id: `msg_${Date.now()}`,
      content: data.answer,
      role: 'assistant',
      timestamp: new Date(),
      sources: data.grounding?.sources || [],
      metadata: {
        agent: data.agent,
        confidence: data.grounding?.confidence ?? 0,
        mode: data.grounding?.mode ?? '',
        ...data.meta,
      },
    };
  }

  // Streaming via NDJSON or SSE (data: {...}) lines
  async sendMessageStreaming(
    message: string,
    userId: string,
    onChunk: (chunk: string, isComplete: boolean) => void,
    onComplete: (fullMessage: Message) => void,
    onError: (error: Error) => void
  ): Promise<void> {
    const clientIP = this.getClientIP();
    const sessionId = userId || `session_${clientIP}_${Date.now()}`;

    try {
      const response = await fetch(apiPath('/api/v1/message/stream'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, user_id: sessionId, locale: 'pt-BR' }),
      });
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response body');

      const decoder = new TextDecoder();
      let buffer = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        // Split by newlines; keep the last partial in buffer
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const raw of lines) {
          const line = raw.trim();
          if (!line) continue;
          const payload = line.startsWith('data: ') ? line.slice(6) : line;
          try {
            const evt: StreamEvent = JSON.parse(payload);
            if (evt.type === 'chunk') {
              onChunk(evt.content, !!evt.is_complete);
            } else if (evt.type === 'complete') {
              const msg: Message = {
                id: `msg_${Date.now()}`,
                content: evt.answer,
                role: 'assistant',
                timestamp: new Date(),
                sources: evt.grounding?.sources || [],
                metadata: {
                  agent: evt.agent,
                  confidence: evt.grounding?.confidence ?? 0,
                  mode: evt.grounding?.mode ?? '',
                  ...evt.meta,
                },
              };
              onComplete(msg);
            } else if (evt.type === 'error') {
              onError(new Error(evt.error));
            }
          } catch (e) {
            // Ignore malformed lines
            // console.warn('Stream parse error:', line);
          }
        }
      }
    } catch (err) {
      onError(err as Error);
    }
  }
}

class SessionApiService {
  private getSessionId(): string {
    // Dynamic require to avoid potential import cycles/SSR issues
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const utils = require('../utils/session');
    return utils.getSessionId();
  }

    async getConversationHistory(): Promise<any[]> {
    try {
      const sessionId = this.getSessionId();
      const response = await axios.get(apiPath(`/api/v1/conversation/${sessionId}`), {
        headers: { 'Cache-Control': 'no-cache' },
      });
      if (response.data && response.data.messages) {
        return response.data.messages.map((msg: any) => {
          // Parse JSON strings back to objects
          let sources = [];
          let metadata = {};

          try {
            if (typeof msg.sources === 'string') {
              sources = JSON.parse(msg.sources);
            } else if (Array.isArray(msg.sources)) {
              sources = msg.sources;
            }
          } catch (e) {
            console.warn('Error parsing sources:', e);
            sources = [];
          }

          try {
            if (typeof msg.metadata === 'string') {
              metadata = JSON.parse(msg.metadata);
            } else if (typeof msg.metadata === 'object') {
              metadata = msg.metadata || {};
            }
          } catch (e) {
            console.warn('Error parsing metadata:', e);
            metadata = {};
          }

          return {
            id: msg.id || `msg_${Date.now()}`,
            content: msg.content || '',
            role: msg.role || 'assistant',
            timestamp: msg.timestamp ? new Date(msg.timestamp) : new Date(),
            sources: sources,
            metadata: metadata,
          };
        });
      }
      return [];
    } catch (e) {
      console.warn('Failed to load conversation history:', e);
      return [];
    }
  }

  async getConversationHistoryBy(sessionId: string): Promise<any[]> {
    try {
      const response = await axios.get(apiPath(`/api/v1/conversation/${sessionId}`), {
        headers: { 'Cache-Control': 'no-cache' },
      });
      if (response.data && response.data.messages) {
        return response.data.messages.map((msg: any) => {
          // Parse JSON strings back to objects
          let sources = [];
          let metadata = {};

          try {
            if (typeof msg.sources === 'string') {
              sources = JSON.parse(msg.sources);
            } else if (Array.isArray(msg.sources)) {
              sources = msg.sources;
            }
          } catch (e) {
            console.warn('Error parsing sources:', e);
            sources = [];
          }

          try {
            if (typeof msg.metadata === 'string') {
              metadata = JSON.parse(msg.metadata);
            } else if (typeof msg.metadata === 'object') {
              metadata = msg.metadata || {};
            }
          } catch (e) {
            console.warn('Error parsing metadata:', e);
            metadata = {};
          }

          return {
            id: msg.id || `msg_${Date.now()}`,
            content: msg.content || '',
            role: msg.role || 'assistant',
            timestamp: msg.timestamp ? new Date(msg.timestamp) : new Date(),
            sources: sources,
            metadata: metadata,
          };
        });
      }
      return [];
    } catch (e) {
      console.warn('Failed to load conversation history by id:', e);
      return [];
    }
  }

  async saveConversation(messages: any[]): Promise<boolean> {
    try {
      const sessionId = this.getSessionId();
      const conversationData = {
        session_id: sessionId,
        messages: messages.map((msg: any) => ({
          id: msg.id,
          content: msg.content,
          role: msg.role,
          timestamp: msg.timestamp instanceof Date ? msg.timestamp.toISOString() : msg.timestamp,
          sources: msg.sources || [],
          metadata: msg.metadata || {},
        })),
      };
  await axios.post(apiPath('/api/v1/conversation'), conversationData);
      return true;
    } catch (e) {
      console.warn('Failed to save conversation:', e);
      return false;
    }
  }

  async clearConversation(): Promise<boolean> {
    try {
      const sessionId = this.getSessionId();
  await axios.delete(apiPath(`/api/v1/conversation/${sessionId}`));
      return true;
    } catch (e) {
      console.warn('Failed to clear conversation:', e);
      return false;
    }
  }

  async deleteConversationById(sessionId: string): Promise<boolean> {
    try {
      await axios.delete(apiPath(`/api/v1/conversation/${sessionId}`));
      return true;
    } catch (e) {
      console.warn('Failed to delete conversation by id:', e);
      return false;
    }
  }

  async getSessionList(): Promise<any[]> {
    try {
  const response = await axios.get(apiPath('/api/v1/sessions'));
      return response.data || [];
    } catch (e) {
      console.warn('Failed to load session list:', e);
      return [];
    }
  }
}

export const chatApi = new ChatApiService();
export const sessionApi = new SessionApiService();
