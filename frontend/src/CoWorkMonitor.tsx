/**
 * CoWork Monitor with Visible Entry Point
 * 
 * Like Claude Code's "Cowork" tab - explicit workflow mode entry
 */

import React, { useState } from 'react';
import { CoworkPanel } from './components';
import { useWorkflow, useSSE } from './hooks';

const CoWorkMonitor: React.FC = () => {
  const [showCowork, setShowCowork] = useState(false);
  const { workflowState, setWorkflowState } = useWorkflow();
  
  useSSE(
    workflowState?.instance_id || null,
    {
      onMessage: (data) => setWorkflowState(data),
    }
  );

  return (
    <div className="app">
      {/* Main chat interface */}
      <header className="app-header">
        <div className="header-tabs">
          <button
            type="button"
            className={!showCowork ? 'active' : ''}
            onClick={() => setShowCowork(false)}
          >
            Chat
          </button>
          <button
            type="button"
            className={showCowork ? 'active' : ''}
            onClick={() => setShowCowork(true)}
          >
            Workflow
            {workflowState && (
              <span className="badge">{workflowState.status}</span>
            )}
          </button>
        </div>
      </header>

      <div className="main-content">
        {/* Chat area - always visible */}
        <div className="chat-area">
          <div className="chat-messages">
            <p>Chat interface here...</p>
          </div>
          <div className="chat-input">
            <input type="text" placeholder="Type a message..." />
          </div>
        </div>

        {/* Cowork Panel - slides in when activated */}
        {showCowork && (
          <CoworkPanel 
            isOpen={showCowork}
            onClose={() => setShowCowork(false)}
            workspaceFiles={[]}
            onRefreshWorkspaceFiles={async () => {}}
          />
        )}

        {/* Or show monitor if workflow is running */}
        {workflowState && !showCowork && (
          <div className="workflow-indicator">
            <span>Workflow running: {workflowState.workflow_id}</span>
            <button onClick={() => setShowCowork(true)}>View</button>
          </div>
        )}
      </div>
    </div>
  );
};

export default CoWorkMonitor;
