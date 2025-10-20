import React, { useState, useEffect, useCallback } from 'react';
import { MessageSquare, Plus, Trash2, User, Bot } from 'lucide-react';
import { Message } from '../types';
import { sessionApi } from '../services/api';

interface SidebarProps {
  messages: Message[];
  onNewChat: () => void;
  onLoadConversation: (sessionId: string) => void;
  onClearChat: () => void;
}

interface ChatSession {
  id: string;
  title: string;
  lastMessage: string;
  timestamp: Date;
  messageCount: number;
}

const Sidebar: React.FC<SidebarProps> = ({
  messages,
  onNewChat,
  onLoadConversation,
  onClearChat
}) => {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [loading, setLoading] = useState(false);
  const [lastMessageCount, setLastMessageCount] = useState(0);
  const loadingRef = React.useRef(false);

  const loadSessions = useCallback(async () => {
    if (loadingRef.current) {
      console.log('⚠️ loadSessions already in progress, skipping...');
      return;
    }

    console.log('🔄 Loading sessions list...');
    try {
      loadingRef.current = true;
      setLoading(true);
      const sessionList = await sessionApi.getSessionList();
      console.log(`✅ Loaded ${sessionList.length} sessions`);
      setSessions(sessionList);
    } catch (error) {
      console.warn('❌ Failed to load sessions:', error);
      setSessions([]);
    } finally {
      loadingRef.current = false;
      setLoading(false);
    }
  }, []); // Sem dependências para evitar loop

  // Debounced version to prevent rapid successive calls
  const debouncedLoadSessions = useCallback(() => {
    if (loadingRef.current) return;

    // Clear any existing timeout
    if ((window as any).__sidebarTimeout) {
      clearTimeout((window as any).__sidebarTimeout);
    }

    // Set new timeout
    (window as any).__sidebarTimeout = setTimeout(() => {
      if (!loadingRef.current) {
        loadSessions();
      }
    }, 100);
  }, [loadSessions]);

  // Load sessions only once on mount
  useEffect(() => {
    loadSessions();
  }, []); // Empty array = executa só uma vez

  // Only reload sessions when the first message is added to an empty conversation
  useEffect(() => {
    const currentMessageCount = messages.length;
    const isFirstMessage = lastMessageCount === 0 && currentMessageCount === 1;

    if (isFirstMessage) {
      console.log('📝 First message added, scheduling session reload...');
      // Wait a bit for the backend to process the session
      setTimeout(() => {
        console.log('🔄 Auto-reloading sessions after first message...');
        debouncedLoadSessions();
      }, 1000); // Increased delay to avoid conflicts
    }

    setLastMessageCount(currentMessageCount);
  }, [messages.length, lastMessageCount, debouncedLoadSessions]);

  const formatTime = (date: Date | string | number) => {
    try {
      const dateObj = date instanceof Date ? date : new Date(date);
      const now = new Date();
      const diff = now.getTime() - dateObj.getTime();
      const hours = Math.floor(diff / 3600000);

      if (hours < 24) {
        return `${Math.max(0, hours)}h`;
      } else {
        const days = Math.floor(hours / 24);
        return `${Math.max(0, days)}d`;
      }
    } catch (error) {
      return 'now';
    }
  };

  const getCurrentSessionTitle = () => {
    if (messages.length === 0) return 'New conversation';

    // Find the first user message that has content
    const firstUserMessage = messages.find(m => m.role === 'user' && m.content?.trim());
    if (firstUserMessage && firstUserMessage.content) {
      const content = firstUserMessage.content.trim();
      return content.length > 25
        ? content.substring(0, 25) + '...'
        : content;
    }

    // Fallback: use assistant response if no user message found
    const firstAssistantMessage = messages.find(m => m.role === 'assistant' && m.content?.trim());
    if (firstAssistantMessage && firstAssistantMessage.content) {
      const content = firstAssistantMessage.content.trim();
      const preview = content.length > 25
        ? content.substring(0, 25) + '...'
        : content;
      return `AI: ${preview}`;
    }

    return 'New conversation';
  };

  const handleNewChat = () => {
    console.log('🆕 Creating new chat...');
    onNewChat();
    // Reload sessions after a short delay to allow the new session to be created
    setTimeout(() => {
      console.log('🔄 Reloading sessions after new chat...');
      debouncedLoadSessions();
    }, 500);
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-content">
          
          {/* New Chat Button */}
          <div className="sidebar-section">
            <button onClick={handleNewChat} className="new-chat-btn">
              <Plus size={16} />
              New chat
            </button>
          </div>

          {/* Divider */}
          <div className="sidebar-divider" />

          {/* Current Session (if has messages) */}
          {messages.length > 0 && (
            <>
              <div className="sidebar-section">
                <div className="section-header">
                  <span className="section-title">Today</span>
                  <button
                    onClick={onClearChat}
                    className="icon-btn danger"
                    title="Clear conversation"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
                
                <div className="chat-item active">
                  <div className="chat-item-content">
                    <div className="chat-title">{getCurrentSessionTitle()}</div>
                  </div>
                </div>
              </div>

              <div className="sidebar-divider" />
            </>
          )}

          {/* Recent Conversations */}
          <div className="sidebar-section">
            {sessions.length > 0 && (
              <div className="section-header">
                <span className="section-title">Previous conversations</span>
              </div>
            )}

            <div className="chat-list">
              {loading ? (
                <div className="loading-state">Loading...</div>
              ) : sessions.length === 0 ? (
                <div className="empty-state">
                  <MessageSquare size={20} className="empty-icon" />
                  <p className="empty-text">Your conversations will appear here</p>
                </div>
              ) : (
                sessions.map((session) => (
                  <div
                    key={session.id}
                    className="chat-item"
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      console.log('🔄 Clicking to load conversation:', session.id);
                      console.log('   Title:', session.title);
                      console.log('   Timestamp:', session.timestamp);
                      onLoadConversation(session.id);
                    }}
                  >
                    <div className="chat-item-content">
                      <div className="chat-title">{session.title}</div>
                      <div className="chat-actions">
                        <span className="chat-time">{formatTime(session.timestamp)}</span>
                        <button
                          className="icon-btn danger"
                          title="Delete conversation"
                          onClick={(e) => {
                            e.stopPropagation();
                            sessionApi.deleteConversationById(session.id).then(() => loadSessions());
                          }}
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Footer */}
          <div className="sidebar-footer">
            <div className="sidebar-divider" />
            <div className="footer-content">
              <div className="footer-item">
                <Bot size={14} />
                <span>InfinitePay Assistant</span>
              </div>
              <div className="footer-item">
                <User size={14} />
                <span>AI Support</span>
              </div>
            </div>
          </div>

        </div>
      </aside>
    );
};

export default Sidebar;
