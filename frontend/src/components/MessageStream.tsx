/**
 * MessageStream — bus messages with filters.
 */

import React, { useState, useMemo } from 'react';
import type { Message } from '../types/cowork';

interface MessageStreamProps {
  messages: Message[];
  maxMessages?: number;
}

type MessageFilter = 'all' | 'direct' | 'broadcast' | 'task' | 'result';

const formatTime = (timestamp: string): string => {
  const date = new Date(timestamp);
  return date.toLocaleTimeString(undefined, { 
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
};

const getMessageTypeStyle = (type: string): string => {
  const styles: Record<string, string> = {
    task: 'msg-task',
    result: 'msg-result',
    critique: 'msg-critique',
    consensus: 'msg-consensus',
    broadcast: 'msg-broadcast',
    direct: 'msg-direct',
  };
  return styles[type] || 'msg-default';
};

export const MessageStream: React.FC<MessageStreamProps> = ({ 
  messages,
  maxMessages = 100,
}) => {
  const [filter, setFilter] = useState<MessageFilter>('all');

  const filteredMessages = useMemo(() => {
    let filtered = messages;
    
    if (filter !== 'all') {
      filtered = messages.filter((m) => m.type === filter);
    }
    
    return filtered.slice(-maxMessages);
  }, [messages, filter, maxMessages]);

  const filters: { key: MessageFilter; label: string }[] = [
    { key: 'all', label: 'All' },
    { key: 'direct', label: 'Direct' },
    { key: 'broadcast', label: 'Broadcast' },
    { key: 'task', label: 'Task' },
    { key: 'result', label: 'Result' },
  ];

  return (
    <div className="message-stream">
      <div className="stream-header">
        <h3>Messages ({filteredMessages.length})</h3>
        
        <div className="filter-tabs">
          {filters.map((f) => (
            <button
              key={f.key}
              className={filter === f.key ? 'active' : ''}
              onClick={() => setFilter(f.key)}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      <div className="message-list">
        {filteredMessages.length === 0 ? (
          <p className="empty">No messages</p>
        ) : (
          filteredMessages.map((msg) => (
            <div 
              key={msg.message_id} 
              className={`message-item ${getMessageTypeStyle(msg.type)}`}
            >
              <div className="message-header">
                <span className="timestamp">{formatTime(msg.timestamp)}</span>
                <span className={`type-badge ${msg.type}`}>{msg.type}</span>
              </div>
              
              <div className="message-route">
                <span className="sender">{msg.sender}</span>
                <span className="arrow"> → </span>
                <span className="receiver">
                  {msg.receiver || 'Broadcast'}
                </span>
              </div>
              
              <div className="message-payload">
                {JSON.stringify(msg.payload, null, 2).slice(0, 200)}
                {JSON.stringify(msg.payload).length > 200 && '...'}
              </div>
              
              {msg.thread_id && (
                <div className="thread-id">
                  Thread: {msg.thread_id}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default MessageStream;
