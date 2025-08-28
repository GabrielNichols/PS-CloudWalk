import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, ExternalLink, Clock, Zap, Target, Trash2, Menu } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { Message } from '../types';
import Sidebar from './Sidebar';

interface ChatInterfaceProps {
  messages: Message[];
  onSendMessage: (message: string) => void;
  onClearChat: () => void;
  isLoading: boolean;
}

const ChatInterface: React.FC<ChatInterfaceProps> = ({ messages, onSendMessage, onClearChat, isLoading }) => {
  const [input, setInput] = useState('');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const toggleSidebar = () => {
    setSidebarCollapsed(!sidebarCollapsed);
  };

  const handleNewChat = () => {
    onClearChat();
    setSidebarCollapsed(true);
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    if (!isLoading && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isLoading]);

  // Close sidebar on mobile when clicking outside
  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth >= 768) {
        setSidebarCollapsed(true);
      }
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim() && !isLoading) {
      onSendMessage(input.trim());
      setInput('');
    }
  };

  const formatMetadata = (metadata: any) => {
    if (!metadata) return null;

    return (
      <div className="flex flex-wrap gap-2 mt-3 text-xs text-gray-400">
        {metadata.agent && (
          <span className="flex items-center gap-1 px-2 py-1 bg-gray-700 rounded">
            <Bot className="w-3 h-3" />
            {metadata.agent}
          </span>
        )}
        {metadata.confidence && (
          <span className="flex items-center gap-1 px-2 py-1 bg-gray-700 rounded">
            <Target className="w-3 h-3" />
            {Math.round(metadata.confidence * 100)}%
          </span>
        )}
        {metadata.latency_ms && (
          <span className="flex items-center gap-1 px-2 py-1 bg-gray-700 rounded">
            <Zap className="w-3 h-3" />
            {metadata.latency_ms}ms
          </span>
        )}
        {metadata.mode && (
          <span className="px-2 py-1 bg-gray-700 rounded">
            {metadata.mode}
          </span>
        )}
      </div>
    );
  };

  const formatSources = (sources: any[]) => {
    if (!sources || sources.length === 0) return null;

    return (
      <div className="mt-4 p-3 bg-gray-800 rounded-lg border-l-4 border-blue-500">
        <h4 className="text-sm font-semibold text-blue-400 mb-2">Sources:</h4>
        <div className="space-y-1">
          {sources.map((source, index) => (
            <a
              key={index}
              href={source.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 text-sm text-blue-300 hover:text-blue-200 transition-colors"
            >
              <ExternalLink className="w-3 h-3" />
              {source.title || source.url}
            </a>
          ))}
        </div>
      </div>
    );
  };

  return (
    <div className="chat-container">
      {/* Sidebar */}
      <Sidebar
        messages={messages}
        onNewChat={handleNewChat}
        onClearChat={onClearChat}
        isCollapsed={sidebarCollapsed}
        onToggleCollapse={toggleSidebar}
      />

      {/* Main Chat Area */}
      <div className="chat-main">

        {/* Header */}
        <div className="chat-header">
          <div className="header-content">
            <button
              onClick={toggleSidebar}
              className="md:hidden p-2 text-gray-400 hover:text-white rounded-lg transition-colors"
              title="Open sidebar"
            >
              <Menu className="w-5 h-5" />
            </button>

            <Bot className="w-8 h-8 text-blue-500" />
            <div>
              <h1 className="header-title">InfinitePay Assistant</h1>
              <p className="header-subtitle">AI-Powered Customer Support</p>
            </div>
          </div>
        </div>

        {/* Messages */}
        <div className="messages-container">
          {messages.length === 0 && (
            <div className="empty-state">
              <Bot className="w-16 h-16 text-gray-600 mx-auto mb-4" />
              <h3 className="empty-title">Welcome to InfinitePay Assistant</h3>
              <p className="empty-subtitle">Ask me anything about our products and services!</p>
            </div>
          )}

          {messages.map((message) => (
            <div key={message.id} className={`message ${message.role}`}>
              {message.role === 'assistant' && (
                <div className="message-avatar">
                  <Bot className="w-5 h-5" />
                </div>
              )}

              <div className="message-content">
                <div className="markdown-content">
                  <ReactMarkdown>{message.content}</ReactMarkdown>
                </div>

                {message.role === 'assistant' && (
                  <>
                    {formatMetadata(message.metadata)}
                    {formatSources(message.sources || [])}
                  </>
                )}

                <div className="message-meta">
                  <Clock className="w-3 h-3" />
                  {message.timestamp instanceof Date
                    ? message.timestamp.toLocaleTimeString()
                    : new Date(message.timestamp || Date.now()).toLocaleTimeString()
                  }
                </div>
              </div>

              {message.role === 'user' && (
                <div className="message-avatar">
                  <User className="w-5 h-5" />
                </div>
              )}
            </div>
          ))}

          {isLoading && (
            <div className="typing-indicator">
              <div className="message-avatar">
                <Bot className="w-5 h-5" />
              </div>
              <div className="typing-content">
                <div className="typing-dots">
                  <div className="typing-dot"></div>
                  <div className="typing-dot"></div>
                  <div className="typing-dot"></div>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="input-container">
          <form onSubmit={handleSubmit} className="input-form">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask me anything about InfinitePay..."
              className="input-field"
              disabled={isLoading}
            />
            <button
              type="submit"
              disabled={!input.trim() || isLoading}
              className="send-button"
            >
              <Send className="w-5 h-5" />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};

export default ChatInterface;
