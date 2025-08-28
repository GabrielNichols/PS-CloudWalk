import { useState, useCallback, useEffect } from 'react';
import { Message, ChatState } from '../types';
import { chatApi, sessionApi } from '../services/api';
import { getSessionId, clearSession } from '../utils/session';

export const useChat = () => {
  const [state, setState] = useState<ChatState>({
    messages: [],
    isLoading: false,
    currentSessionId: null,
  });

  // Load messages from backend on mount
  useEffect(() => {
    const loadConversation = async () => {
      try {
        const sessionId = getSessionId();
        const conversationHistory = await sessionApi.getConversationHistory();

        setState(prev => ({
          ...prev,
          messages: conversationHistory,
          currentSessionId: sessionId,
        }));
      } catch (error) {
        console.warn('Failed to load conversation history:', error);
        // Fallback to empty state
        setState(prev => ({
          ...prev,
          currentSessionId: getSessionId(),
        }));
      }
    };

    loadConversation();
  }, []);

  // Frontend no longer posts full conversation automatically; backend already persists per-message.

  const sendMessage = useCallback(async (content: string) => {
    const sessionId = state.currentSessionId || getSessionId();

    // Add user message
    const userMessage: Message = {
      id: `user_${Date.now()}`,
      content,
      role: 'user',
      timestamp: new Date(),
    };

    setState(prev => ({
      ...prev,
      messages: [...prev.messages, userMessage],
      isLoading: true,
      currentSessionId: sessionId,
    }));

    try {
      // Try streaming first with a single placeholder message
      let streamingSupported = true;
      const placeholderId = `assistant_${Date.now()}`;

      // Create placeholder assistant message once
      setState(prev => ({
        ...prev,
        messages: [
          ...prev.messages,
          {
            id: placeholderId,
            content: '',
            role: 'assistant',
            timestamp: new Date(),
            isStreaming: true,
          } as Message,
        ],
      }));

      try {
        await chatApi.sendMessageStreaming(
          content,
          sessionId,
          (chunk, isComplete) => {
            setState(prev => ({
              ...prev,
              messages: prev.messages.map(m =>
                m.id === placeholderId
                  ? { ...m, content: (m.content || '') + chunk, isStreaming: !isComplete }
                  : m
              ),
            }));
          },
          (fullMessage) => {
            setState(prev => ({
              ...prev,
              messages: prev.messages.map(m => (m.id === placeholderId ? { ...fullMessage, id: placeholderId, isStreaming: false } : m)),
              isLoading: false,
            }));
          },
          (error) => {
            console.warn('Streaming failed, falling back to regular API:', error);
            streamingSupported = false;
          }
        );
      } catch (streamingError) {
        streamingSupported = false;
      }

      if (!streamingSupported) {
        const assistantMessage = await chatApi.sendMessage(content, sessionId);
        setState(prev => ({
          ...prev,
          messages: prev.messages.map(m => (m.id === placeholderId ? assistantMessage : m)),
          isLoading: false,
        }));
      }

    } catch (error) {
      console.error('Failed to send message:', error);

      // Add error message
      const errorMessage: Message = {
        id: `error_${Date.now()}`,
        content: 'Sorry, I encountered an error. Please try again.',
        role: 'assistant',
        timestamp: new Date(),
        metadata: { agent: 'Error' },
      };

      setState(prev => ({
        ...prev,
        messages: [...prev.messages, errorMessage],
        isLoading: false,
      }));
    }
  }, [state.currentSessionId]);

  const clearChat = useCallback(async () => {
    try {
      // Clear conversation on backend
      await sessionApi.clearConversation();
    } catch (error) {
      console.warn('Failed to clear conversation on backend:', error);
    }

    // Clear local session data
    clearSession();

    setState({
      messages: [],
      isLoading: false,
      currentSessionId: getSessionId(), // Generate new session
    });
  }, []);

  return {
    messages: state.messages,
    isLoading: state.isLoading,
    sendMessage,
    clearChat,
  };
};
