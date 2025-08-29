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

    // Add user message to UI immediately
    const userMessage: Message = {
      id: `user_${Date.now()}`,
      content,
      role: 'user',
      timestamp: new Date(),
    };

    // Create placeholder assistant message
    const placeholderId = `assistant_${Date.now()}`;
    const placeholderMessage: Message = {
      id: placeholderId,
      content: '',
      role: 'assistant',
      timestamp: new Date(),
      isStreaming: true,
    };

    setState(prev => ({
      ...prev,
      messages: [...prev.messages, userMessage, placeholderMessage],
      isLoading: true,
      currentSessionId: sessionId,
    }));

    try {
      // Use streaming API exclusively to avoid duplication
      await chatApi.sendMessageStreaming(
        content,
        sessionId,
        (chunk, isComplete) => {
          // Update streaming content
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
          // Replace placeholder with final message
          setState(prev => ({
            ...prev,
            messages: prev.messages.map(m =>
              m.id === placeholderId
                ? { ...fullMessage, id: placeholderId, isStreaming: false }
                : m
            ),
            isLoading: false,
          }));
        },
        (error) => {
          console.error('Streaming failed:', error);
          // Replace placeholder with error message
          const errorMessage: Message = {
            id: placeholderId,
            content: 'Sorry, I encountered an error. Please try again.',
            role: 'assistant',
            timestamp: new Date(),
            metadata: { agent: 'Error' },
          };

          setState(prev => ({
            ...prev,
            messages: prev.messages.map(m =>
              m.id === placeholderId ? errorMessage : m
            ),
            isLoading: false,
          }));
        }
      );

    } catch (error) {
      console.error('Failed to send message:', error);

      // Replace placeholder with error message
      const errorMessage: Message = {
        id: placeholderId,
        content: 'Sorry, I encountered an error. Please try again.',
        role: 'assistant',
        timestamp: new Date(),
        metadata: { agent: 'Error' },
      };

      setState(prev => ({
        ...prev,
        messages: prev.messages.map(m =>
          m.id === placeholderId ? errorMessage : m
        ),
        isLoading: false,
      }));
    }
  }, [state.currentSessionId]);

  const loadConversation = useCallback(async (sessionId: string) => {
    try {
      setState(prev => ({
        ...prev,
        isLoading: true,
        messages: [], // Clear current messages while loading
        currentSessionId: sessionId,
      }));

      // Load conversation history from backend
      const conversationHistory = await sessionApi.getConversationHistoryBy(sessionId);

      setState(prev => ({
        ...prev,
        messages: conversationHistory,
        isLoading: false,
        currentSessionId: sessionId,
      }));

      console.log(`Loaded conversation with ${conversationHistory.length} messages for session ${sessionId}`);
    } catch (error) {
      console.error('Failed to load conversation:', error);
      setState(prev => ({
        ...prev,
        isLoading: false,
      }));
    }
  }, []);

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
    loadConversation,
    clearChat,
  };
};
