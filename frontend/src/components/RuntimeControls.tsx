/**
 * RuntimeControls — pause / resume / stop workflow.
 */

import React from 'react';

interface RuntimeControlsProps {
  status: string;
  onPause: () => void;
  onResume: () => void;
  onStop: () => void;
  isLoading?: boolean;
}

export const RuntimeControls: React.FC<RuntimeControlsProps> = ({
  status,
  onPause,
  onResume,
  onStop,
  isLoading = false,
}) => {
  const isRunning = status === 'running';
  const isPaused = status === 'paused';

  return (
    <div className="runtime-controls">
      {isRunning && (
        <button 
          onClick={onPause}
          disabled={isLoading}
          className="btn btn-warning"
        >
          Pause
        </button>
      )}
      
      {isPaused && (
        <button 
          onClick={onResume}
          disabled={isLoading}
          className="btn btn-primary"
        >
          Resume
        </button>
      )}
      
      {(isRunning || isPaused) && (
        <button 
          onClick={onStop}
          disabled={isLoading}
          className="btn btn-danger"
        >
          Stop
        </button>
      )}
    </div>
  );
};

export default RuntimeControls;
