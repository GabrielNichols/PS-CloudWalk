import React, { useState, useEffect } from 'react';
import { MessageSquare, Plus, Trash2, Clock, User, Bot, ExternalLink } from 'lucide-react';
import { Message } from '../types';
import { sessionApi } from '../services/api';

interface SidebarProps {
  messages: Message[];
  onNewChat: () => void;
  onClearChat: () => void;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
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
  onClearChat,
  isCollapsed,
  onToggleCollapse
}) => {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadSessions();
  }, []);

  const loadSessions = async () => {
    try {
      setLoading(true);
      const sessionList = await sessionApi.getSessionList();
      setSessions(sessionList);
    } catch (error) {
      console.warn('Failed to load sessions:', error);
      // Fallback to empty sessions list
      setSessions([]);
    } finally {
      setLoading(false);
    }
  };

  const formatTime = (date: Date | string | number) => {
    try {
      const dateObj = date instanceof Date ? date : new Date(date);
      const now = new Date();
      const diff = now.getTime() - dateObj.getTime();
      const hours = Math.floor(diff / 3600000);

      if (hours < 24) {
        return `${Math.max(0, hours)}h ago`;
      } else {
        const days = Math.floor(hours / 24);
        return `${Math.max(0, days)}d ago`;
      }
    } catch (error) {
      return 'now';
    }
  };

  const getCurrentSessionTitle = () => {
    if (messages.length === 0) return 'New Chat';

    const firstUserMessage = messages.find(m => m.role === 'user');
    if (firstUserMessage) {
      return firstUserMessage.content.length > 30
        ? firstUserMessage.content.substring(0, 30) + '...'
        : firstUserMessage.content;
    }

    return 'New Chat';
  };

  const handleNewChat = () => {
    onNewChat();
    // Reload sessions after creating new chat
    setTimeout(() => loadSessions(), 1000);
  };

  return (
    <>
      {/* Overlay for mobile */}
      {!isCollapsed && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 z-40 md:hidden"
          onClick={onToggleCollapse}
        />
      )}

      {/* Sidebar */}
      <div className={`sidebar ${isCollapsed ? 'collapsed' : ''}`}>

        <div className="flex flex-col h-full">
          {/* Header */}
          <div className="sidebar-header">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center">
                  <Bot className="w-5 h-5 text-white" />
                </div>
                <div>
                  <h2 className="sidebar-title">Chat History</h2>
                  <p className="sidebar-subtitle">{sessions.length} conversations</p>
                </div>
              </div>
              <button
                onClick={onToggleCollapse}
                className="md:hidden p-1 text-gray-400 hover:text-white"
              >
                <ExternalLink className="w-5 h-5" />
              </button>
            </div>

            <button
              onClick={handleNewChat}
              className="new-chat-button"
            >
              <Plus className="w-4 h-4" />
              New Chat
            </button>
          </div>

          {/* Current Session */}
          <div className="current-session">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-gray-400 font-medium">CURRENT SESSION</span>
              {messages.length > 0 && (
                <button
                  onClick={onClearChat}
                  className="p-1 text-gray-400 hover:text-red-400 transition-colors"
                  title="Clear current chat"
                >
                  <Trash2 className="w-3 h-3" />
                </button>
              )}
            </div>

            <div className="flex items-center gap-2 p-2 bg-gray-800 rounded-lg">
              <MessageSquare className="w-4 h-4 text-blue-400" />
              <div className="flex-1 min-w-0">
                <p className="text-sm text-white truncate">{getCurrentSessionTitle()}</p>
                <p className="text-xs text-gray-400">{messages.length} messages</p>
              </div>
            </div>
          </div>

          {/* Chat History */}
          <div className="conversations-list">
            <h3 className="text-xs text-gray-400 font-medium mb-3">RECENT CONVERSATIONS</h3>

            <div className="space-y-2">
              {loading ? (
                <div className="text-center py-8 text-gray-400">
                  <div className="animate-spin w-4 h-4 border-2 border-gray-600 border-t-gray-400 rounded-full mx-auto mb-2"></div>
                  Loading conversations...
                </div>
              ) : sessions.length === 0 ? (
                <div className="text-center py-8 text-gray-400">
                  <MessageSquare className="w-8 h-8 mx-auto mb-2 opacity-50" />
                  <p className="text-sm">No conversations yet</p>
                  <p className="text-xs mt-1">Start a new chat to see your history</p>
                </div>
              ) : (
                sessions.map((session) => (
                <div
                  key={session.id}
                  className="conversation-item"
                  onClick={() => {
                    // In a real app, this would load the session
                    console.log('Load session:', session.id);
                  }}
                >
                  <div className="flex items-start justify-between mb-1">
                    <h4 className="conversation-title">
                      {session.title}
                    </h4>
                    <span className="text-xs text-gray-400 ml-2 flex-shrink-0">
                      {session.messageCount}
                    </span>
                  </div>

                  <p className="conversation-preview">
                    {session.lastMessage}
                  </p>

                  <div className="conversation-meta">
                    <div className="flex items-center gap-1 text-xs text-gray-500">
                      <Clock className="w-3 h-3" />
                      {formatTime(session.timestamp)}
                    </div>

                    <button
                      className="opacity-0 group-hover:opacity-100 p-1 text-gray-400 hover:text-red-400 transition-all"
                      title="Delete conversation"
                      onClick={(e) => {
                        e.stopPropagation();
                        console.log('Delete session:', session.id);
                      }}
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                </div>
                ))
              )}
            </div>
          </div>

          {/* Footer */}
          <div className="sidebar-footer">
            <div className="footer-item">
              <Bot className="w-3 h-3" />
              <span>InfinitePay Assistant</span>
            </div>
            <div className="footer-item">
              <User className="w-3 h-3" />
              <span>AI-Powered Support</span>
            </div>
          </div>
        </div>
      </div>
    </>
  );
};

export default Sidebar;
