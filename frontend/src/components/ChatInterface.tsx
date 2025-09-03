import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, ExternalLink, Clock, Zap, Target, ChevronDown } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { Message } from '../types';
import Sidebar from './Sidebar';

// Helper function to make incomplete markdown safe for rendering during streaming
const makeMarkdownSafe = (content: string, isStreaming: boolean): string => {
  if (!content) return '';
  
  // If not streaming, return content as-is
  if (!isStreaming) return content;
  
  let safeContent = content;
  
  try {
    // Fix incomplete bold formatting
    const boldMatches = (safeContent.match(/\*\*/g) || []).length;
    if (boldMatches % 2 !== 0) {
      safeContent += '**';
    }
    
    // Fix incomplete italic formatting (avoid conflict with bold)
    const italicMatches = (safeContent.match(/(?<!\*)\*(?!\*)/g) || []).length;
    if (italicMatches % 2 !== 0) {
      safeContent += '*';
    }
    
    // Fix incomplete code blocks
    const codeBlockMatches = (safeContent.match(/```/g) || []).length;
    if (codeBlockMatches % 2 !== 0) {
      safeContent += '\n```';
    }
    
    // Fix incomplete inline code (simpler approach)
    const backtickCount = (safeContent.match(/`/g) || []).length;
    if (backtickCount % 2 !== 0) {
      safeContent += '`';
    }
    
    // Fix incomplete headers that might break
    if (safeContent.endsWith('#')) {
      safeContent += ' ';
    }
    
  } catch (error) {
    console.warn('Error processing markdown:', error);
    return content; // Return original if processing fails
  }
  
  return safeContent;
};

// Custom component for streaming markdown that forces updates
const StreamingMarkdown: React.FC<{ content: string; isStreaming: boolean }> = ({ content, isStreaming }) => {
  const [renderKey, setRenderKey] = useState(0);
  
  // Force re-render every time content changes during streaming
  useEffect(() => {
    if (isStreaming) {
      setRenderKey(prev => prev + 1);
    }
  }, [content, isStreaming]);
  
  return (
    <ReactMarkdown
      key={isStreaming ? `streaming-${renderKey}` : 'static'}
      skipHtml={false}
      components={{
        p: ({ children }) => <p style={{ margin: '0 0 1em 0', minHeight: isStreaming ? '1.2em' : 'auto' }}>{children}</p>,
        code: ({ children, className, ...props }: any) => {
          const inline = props.inline || false;
          return inline ? (
            <code className={className} style={{ 
              background: 'rgba(255,255,255,0.1)', 
              padding: '2px 4px', 
              borderRadius: '3px' 
            }}>
              {children}
            </code>
          ) : (
            <pre style={{ 
              background: 'rgba(255,255,255,0.1)', 
              padding: '12px', 
              borderRadius: '6px',
              overflow: 'auto'
            }}>
              <code className={className}>{children}</code>
            </pre>
          );
        },
        ul: ({ children }) => <ul style={{ margin: '0 0 1em 0', paddingLeft: '1.5em' }}>{children}</ul>,
        ol: ({ children }) => <ol style={{ margin: '0 0 1em 0', paddingLeft: '1.5em' }}>{children}</ol>,
        li: ({ children }) => <li style={{ margin: '0.25em 0' }}>{children}</li>,
      }}
    >
      {makeMarkdownSafe(content, isStreaming)}
    </ReactMarkdown>
  );
};

interface ChatInterfaceProps {
  messages: Message[];
  onSendMessage: (message: string) => void;
  onLoadConversation: (sessionId: string) => void;
  onClearChat: () => void;
  isLoading: boolean;
}

const ChatInterface: React.FC<ChatInterfaceProps> = ({ messages, onSendMessage, onLoadConversation, onClearChat, isLoading }) => {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const [openDebugIds, setOpenDebugIds] = useState<Record<string, boolean>>({});

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const handleNewChat = () => {
    onClearChat();
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    if (!isLoading && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isLoading]);

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (input.trim() && !isLoading) {
      onSendMessage(input.trim());
      setInput('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const formatMetadata = (metadata: any) => {
    if (!metadata) return null;

    return (
      <div className="meta-badges">
        {metadata.agent && (
          <span className="badge">
            <Bot size={12} />
            <span>{metadata.agent}</span>
          </span>
        )}
        {typeof metadata.confidence === 'number' && (
          <span className="badge">
            <Target size={12} />
            <span>{Math.round(metadata.confidence * 100)}%</span>
          </span>
        )}
        {metadata.latency_ms && (
          <span className="badge">
            <Zap size={12} />
            <span>{metadata.latency_ms}ms</span>
          </span>
        )}
        {metadata.mode && <span className="badge plain">{metadata.mode}</span>}
      </div>
    );
  };

  const formatSources = (sources: any[]) => {
    if (!sources || sources.length === 0) return null;

    return (
      <div className="message-sources">
        <h4 className="sources-title">Sources:</h4>
        <div>
          {sources.map((source, index) => (
            <a key={index} href={source.url} target="_blank" rel="noopener noreferrer" className="source-link">
              <ExternalLink size={12} />
              {source.title || source.url}
            </a>
          ))}
        </div>
      </div>
    );
  };

  const renderDebug = (message: Message) => {
  const hasDebug = message.metadata?.steps || message.metadata?.retrieval || message.metadata?.tokens || (message.metadata as any)?.route_trace;
    if (!hasDebug) return null;

    const isOpen = !!openDebugIds[message.id];
    const toggle = () => setOpenDebugIds((m) => ({ ...m, [message.id]: !isOpen }));

    return (
      <div className="debug-panel">
        <button className="debug-toggle" onClick={toggle} aria-expanded={isOpen}>
          <ChevronDown size={14} className={`chevron ${isOpen ? 'open' : ''}`} />
          Details
        </button>
        {isOpen && (
          <div className="debug-content">
            {message.metadata?.steps && (
              <div className="debug-section">
                <div className="debug-title">Reasoning/Steps</div>
                <ol>
                  {(message.metadata.steps as string[]).map((s, i) => (
                    <li key={i}>{s}</li>
                  ))}
                </ol>
              </div>
            )}
            {(message.metadata as any)?.route_trace && (
              <div className="debug-section">
                <div className="debug-title">Route trace</div>
                <ol>
                  {((message.metadata as any).route_trace as any[]).map((r, i) => (
                    <li key={i}>
                      <strong>{r.decision}</strong> · conf {Math.round((r.confidence || 0) * 100)}% · {r.reason}
                    </li>
                  ))}
                </ol>
              </div>
            )}
            {message.metadata?.retrieval && (
              <div className="debug-section">
                <div className="debug-title">Retrieval</div>
                <pre>{JSON.stringify(message.metadata.retrieval, null, 2)}</pre>
              </div>
            )}
            {typeof message.metadata?.tokens === 'number' && (
              <div className="debug-section">
                <div className="debug-title">Token usage</div>
                <div>{message.metadata.tokens}</div>
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="chat-container">
      {/* Sidebar */}
      <Sidebar
        messages={messages}
        onNewChat={handleNewChat}
        onLoadConversation={onLoadConversation}
        onClearChat={onClearChat}
      />
      {/* Main Chat Area */}
      <div className="chat-main">
        {/* Top bar (minimal, ChatGPT-like) */}
        <div className="topbar">
          <div className="topbar-title">InfinitePay Assistant</div>
        </div>

        {/* Thread */}
        <div className="thread">
          <div className={`thread-inner ${messages.length === 0 ? 'empty' : ''}`}>
          {messages.length === 0 && (
            <div className="empty-state">
              <div className="empty-logo"><Bot size={56} /></div>
              <h3 className="empty-title">Welcome to InfinitePay Assistant</h3>
              <p className="empty-subtitle">Ask me anything about our products and services!</p>
            </div>
          )}

          {messages.map((message) => (
            <div key={message.id} className={`msg ${message.role}`}>
              <div className="avatar">
                {message.role === 'assistant' ? 'AI' : 'You'}
              </div>
              <div className="bubble">
                <div className="markdown-content">
                  <StreamingMarkdown 
                    content={message.content || ''} 
                    isStreaming={message.isStreaming || false} 
                  />
                  {message.isStreaming && (
                    <span className="streaming-cursor">|</span>
                  )}
                </div>
                {message.role === 'assistant' && (
                  <>
                    {formatMetadata(message.metadata)}
                    {formatSources(message.sources || [])}
                    {renderDebug(message)}
                  </>
                )}
                <div className="time">
                  <Clock className="w-3 h-3" />
                  {message.timestamp instanceof Date
                    ? message.timestamp.toLocaleTimeString()
                    : new Date(message.timestamp || Date.now()).toLocaleTimeString()}
                </div>
              </div>
            </div>
          ))}

          {isLoading && !messages.some(m => m.isStreaming) && (
            <div className="msg assistant">
              <div className="avatar">AI</div>
              <div className="bubble">
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
        </div>

        {/* Composer */}
        <div className="composer">
          <form onSubmit={handleSubmit} className="composer-inner">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask anything about InfinitePay..."
              className="composer-input"
              rows={1}
              disabled={isLoading}
            />
            <button
              type="submit"
              disabled={!input.trim() || isLoading}
              className="composer-send"
              aria-label="Send"
            >
              <Send size={16} />
            </button>
          </form>
          <div className="composer-hint">Press Enter to send • Shift+Enter to break line</div>
        </div>
      </div>
    </div>
  );
};

export default ChatInterface;
