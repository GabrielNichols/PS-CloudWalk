import React, { useEffect } from 'react';
import ChatInterface from './components/ChatInterface';
import { useChat } from './hooks/useChat';

function App() {
  const { messages, isLoading, sendMessage, loadConversation, clearChat } = useChat();

  // Log inicial para debug
  useEffect(() => {
    console.log('🚀 App component mounted');
    return () => {
      console.log('🛑 App component unmounting');
    };
  }, []);

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