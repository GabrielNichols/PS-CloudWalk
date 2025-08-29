import React from 'react';
import ChatInterface from './components/ChatInterface';
import { useChat } from './hooks/useChat';

function App() {
  const { messages, isLoading, sendMessage, loadConversation, clearChat } = useChat();

  return (
    <ChatInterface
      messages={messages}
      onSendMessage={sendMessage}
      onLoadConversation={loadConversation}
      onClearChat={clearChat}
      isLoading={isLoading}
    />
  );
}

export default App;