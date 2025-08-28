import React from 'react';
import ChatInterface from './components/ChatInterface';
import { useChat } from './hooks/useChat';

function App() {
  const { messages, isLoading, sendMessage, clearChat } = useChat();

  return (
    <ChatInterface
      messages={messages}
      onSendMessage={sendMessage}
      onClearChat={clearChat}
      isLoading={isLoading}
    />
  );
}

export default App;