import axios from 'axios';
import { Message } from '../types';

const API_BASE_URL = process.env.REACT_APP_API_URL ||
  (process.env.NODE_ENV === 'production'
    ? ''
    : 'http://localhost:8000');

interface ApiResponse {
  ok: boolean;
  agent: string;
  answer: string;
  grounding?: {
    mode: string;
    sources?: Array<{
      url: string;
      title?: string;
    }>;
    confidence: number;
  };
  meta?: any;
}

class ChatApiService {
  private getClientIP(): string {
    // Fallback para desenvolvimento - em produção o backend pode detectar o IP
    return '127.0.0.1';
  }

  async sendMessage(message: string, userId?: string): Promise<Message> {
    const clientIP = this.getClientIP();
    const sessionId = userId || `session_${clientIP}_${Date.now()}`;

    try {
      const response = await axios.post<ApiResponse>(`${API_BASE_URL}/api/v1/message`, {
        message,
        user_id: sessionId,
      });

      const data = response.data;

      if (!data.ok) {
        throw new Error('API returned error status');
      }

      return {
        id: `msg_${Date.now()}`,
        content: data.answer,
        role: 'assistant',
        timestamp: new Date(),
        sources: data.grounding?.sources || [],
        metadata: {
          agent: data.agent,
          confidence: data.grounding?.confidence || 0,
          mode: data.grounding?.mode || '',
          ...data.meta,
        },
      };
    } catch (error) {
      console.error('API Error:', error);
      throw new Error('Failed to send message');
    }
  }

  // Streaming version using Server-Sent Events
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
      const response = await fetch(`${API_BASE_URL}/api/v1/message/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message,
          user_id: sessionId,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('No response body');
      }

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();

        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Process complete SSE messages
        const lines = buffer.split('\n');
        buffer = lines.pop() || ''; // Keep incomplete line in buffer

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6)); // Remove 'data: ' prefix

              if (data.type === 'chunk') {
                onChunk(data.content, data.is_complete);
              } else if (data.type === 'complete') {
                const message: Message = {
                  id: `msg_${Date.now()}`,
                  content: data.answer,
                  role: 'assistant',
                  timestamp: new Date(),
                  sources: data.grounding?.sources || [],
                  metadata: {
                    agent: data.agent,
                    confidence: data.grounding?.confidence || 0,
                    mode: data.grounding?.mode || '',
                    ...data.meta,
                  },
                };
                onComplete(message);
              } else if (data.type === 'error') {
                onError(new Error(data.error));
              }
            } catch (parseError) {
              console.warn('Failed to parse SSE data:', line);
            }
          }
        }
      }
    } catch (error) {
      onError(error as Error);
    }
  }
}

// Session management service
class SessionApiService {
  private getSessionId(): string {
    const { getSessionId } = require('../utils/session');
    return getSessionId();
  }

  async getConversationHistory(): Promise<any[]> {
    try {
      const sessionId = this.getSessionId();
      const response = await axios.get(`${API_BASE_URL}/api/v1/conversation/${sessionId}`, {
        headers: {
          'Cache-Control': 'no-cache'
        }
      });

      if (response.data && response.data.messages) {
        return response.data.messages.map((msg: any) => ({
          id: msg.id || `msg_${Date.now()}`,
          content: msg.content || '',
          role: msg.role || 'assistant',
          timestamp: msg.timestamp ? new Date(msg.timestamp) : new Date(),
          sources: msg.sources || [],
          metadata: msg.metadata || {}
        }));
      }

      return [];
    } catch (error) {
      console.warn('Failed to load conversation history:', error);
      return [];
    }
  }

  async saveConversation(messages: any[]): Promise<boolean> {
    try {
      const sessionId = this.getSessionId();
      const conversationData = {
        session_id: sessionId,
        messages: messages.map(msg => ({
          id: msg.id,
          content: msg.content,
          role: msg.role,
          timestamp: msg.timestamp instanceof Date ? msg.timestamp.toISOString() : msg.timestamp,
          sources: msg.sources || [],
          metadata: msg.metadata || {}
        }))
      };

      await axios.post(`${API_BASE_URL}/api/v1/conversation`, conversationData);
      return true;
    } catch (error) {
      console.warn('Failed to save conversation:', error);
      return false;
    }
  }

  async clearConversation(): Promise<boolean> {
    try {
      const sessionId = this.getSessionId();
      await axios.delete(`${API_BASE_URL}/api/v1/conversation/${sessionId}`);
      return true;
    } catch (error) {
      console.warn('Failed to clear conversation:', error);
      return false;
    }
  }

  async getSessionList(): Promise<any[]> {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/v1/sessions`);
      return response.data || [];
    } catch (error) {
      console.warn('Failed to load session list:', error);
      return [];
    }
  }
}

export const chatApi = new ChatApiService();
export const sessionApi = new SessionApiService();
