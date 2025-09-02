/**
 * Session management utilities for IP-based sessions
 */

export const getClientFingerprint = (): string => {
  // Create a fingerprint based on available browser information
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d');
  ctx?.fillText('fingerprint', 10, 10);

  const fingerprint = [
    navigator.userAgent,
    navigator.language,
    (typeof window !== 'undefined' && window.screen)
      ? `${window.screen.width}x${window.screen.height}`
      : 'unknown',
    new Date().getTimezoneOffset(),
    !!window.sessionStorage,
    !!window.localStorage,
    !!window.indexedDB,
    canvas.toDataURL(),
  ].join('|');

  return btoa(fingerprint).substring(0, 32);
};

export const getSessionId = (): string => {
  // Try to get existing session ID from localStorage
  let sessionId = localStorage.getItem('chat_session_id');

  if (!sessionId) {
    // Generate new session ID based on fingerprint and timestamp
    const fingerprint = getClientFingerprint();
    const timestamp = Date.now();
    sessionId = `session_${fingerprint}_${timestamp}`;
    localStorage.setItem('chat_session_id', sessionId);
  }

  return sessionId;
};

export const clearSession = (): void => {
  localStorage.removeItem('chat_session_id');
  localStorage.removeItem('chat_messages');
};

// Emergency function to clear corrupted data (can be called from browser console)
export const emergencyClearAllData = (): void => {
  try {
    localStorage.clear();
    console.log('✅ All localStorage data cleared successfully');
    console.log('🔄 Please refresh the page to start fresh');
  } catch (error) {
    console.error('❌ Failed to clear localStorage:', error);
  }
};

// Make emergency function available globally for debugging
if (typeof window !== 'undefined') {
  (window as any).emergencyClearAllData = emergencyClearAllData;
}

export const validateAndFixMessages = (messages: any[]): any[] => {
  return messages.map(message => {
    // Ensure timestamp is a valid Date object
    let timestamp = message.timestamp;
    if (!(timestamp instanceof Date)) {
      try {
        timestamp = new Date(timestamp);
        if (isNaN(timestamp.getTime())) {
          timestamp = new Date(); // Fallback to current date
        }
      } catch (error) {
        timestamp = new Date(); // Fallback to current date
      }
    }

    return {
      ...message,
      timestamp,
      // Ensure other required fields exist
      id: message.id || `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      content: message.content || '',
      role: message.role || 'assistant',
    };
  });
};

export const saveMessagesToStorage = (messages: any[]): void => {
  try {
    // Convert Date objects to ISO strings before saving
    const messagesToSave = messages.map(message => ({
      ...message,
      timestamp: message.timestamp instanceof Date
        ? message.timestamp.toISOString()
        : message.timestamp
    }));
    localStorage.setItem('chat_messages', JSON.stringify(messagesToSave));
  } catch (error) {
    console.warn('Failed to save messages to localStorage:', error);
  }
};

export const loadMessagesFromStorage = (): any[] => {
  try {
    const stored = localStorage.getItem('chat_messages');
    if (!stored) return [];

    const messages = JSON.parse(stored);

    // Convert ISO strings back to Date objects and validate
    const messagesWithDates = messages.map((message: any) => ({
      ...message,
      timestamp: message.timestamp
        ? new Date(message.timestamp)
        : new Date() // Fallback to current date if timestamp is missing
    }));

    // Validate and fix any corrupted messages
    return validateAndFixMessages(messagesWithDates);
  } catch (error) {
    console.warn('Failed to load messages from localStorage:', error);
    return [];
  }
};
