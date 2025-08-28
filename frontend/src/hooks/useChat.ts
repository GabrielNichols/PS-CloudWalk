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

  // Save messages to backend whenever they change
  useEffect(() => {
    if (state.messages.length > 0) {
      // Debounce saves to avoid too many API calls
      const saveTimer = setTimeout(async () => {
        try {
          await sessionApi.saveConversation(state.messages);
        } catch (error) {
          console.warn('Failed to save conversation to backend:', error);
        }
      }, 1000); // Wait 1 second after last change

      return () => clearTimeout(saveTimer);
    }
  }, [state.messages]);

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
      // Try streaming first
      let streamingSupported = true;
      let streamingMessageId: string | null = null;

      try {
        await chatApi.sendMessageStreaming(
          content,
          sessionId,
          (chunk, isComplete) => {
            // Handle streaming chunks
            setState(prev => {
              const messages = [...prev.messages];
              let lastMessage = messages[messages.length - 1];

              if (lastMessage?.role === 'assistant' && lastMessage.isStreaming) {
                // Update existing streaming message
                lastMessage.content += chunk;
                if (isComplete) {
                  lastMessage.isStreaming = false;
                }
              } else {
                // Create new streaming message
                const newMessage: Message = {
                  id: `assistant_${Date.now()}`,
                  content: chunk,
                  role: 'assistant',
                  timestamp: new Date(),
                  isStreaming: !isComplete,
                };
                messages.push(newMessage);
                streamingMessageId = newMessage.id;
              }

              return { ...prev, messages };
            });
          },
          (fullMessage) => {
            // Streaming completed successfully
            setState(prev => ({
              ...prev,
              messages: prev.messages.map(msg =>
                msg.id === streamingMessageId ? { ...fullMessage, isStreaming: false } : msg
              ),
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

      // Fallback to regular API if streaming fails
      if (!streamingSupported) {
        const assistantMessage = await chatApi.sendMessage(content, sessionId);

        setState(prev => ({
          ...prev,
          messages: [...prev.messages, assistantMessage],
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
