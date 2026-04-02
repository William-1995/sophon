/**
 * AgentPanel — list agent runtime state.
 */

import React from 'react';
import type { AgentState } from '../types/cowork';

interface AgentPanelProps {
  agents: Record<string, AgentState>;
}

const getStatusStyle = (status: string): string => {
  const styles: Record<string, string> = {
    idle: 'status-idle',
    working: 'status-working',
    waiting: 'status-waiting',
    dead: 'status-dead',
  };
  return styles[status] || 'status-unknown';
};

export const AgentPanel: React.FC<AgentPanelProps> = ({ agents }) => {
  const agentList = Object.values(agents);

  if (agentList.length === 0) {
    return (
      <div className="agent-panel empty">
        <p>No active agents</p>
      </div>
    );
  }

  return (
    <div className="agent-panel">
      <h3>Agents ({agentList.length})</h3>
      
      <div className="agent-list">
        {agentList.map((agent) => (
          <div key={agent.agent_id} className="agent-card">
            <div className="agent-header">
              <span className="agent-id">{agent.agent_id}</span>
              <span className={`agent-status ${getStatusStyle(agent.status)}`}>
                {agent.status}
              </span>
            </div>
            
            <div className="agent-info">
              <div>
                <span className="label">Type:</span>
                <span>{agent.agent_type}</span>
              </div>
              
              <div>
                <span className="label">Role:</span>
                <span>{agent.role}</span>
              </div>
              
              {agent.current_task && (
                <div>
                  <span className="label">Task:</span>
                  <span className="task-name">{agent.current_task}</span>
                </div>
              )}
              
              <div className="agent-stats">
                <span title="Messages">💬 {agent.message_count}</span>
                <span title="Tasks">📋 {agent.task_count}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default AgentPanel;
