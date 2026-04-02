import React, { useState, useMemo } from 'react';

interface WorkflowInput {
  name: string;
  label: string;
  type: 'text' | 'number' | 'file' | 'select' | 'textarea' | 'multiselect';
  required?: boolean;
  default?: string | number;
  multiple?: boolean;
  options?: string[];
}

interface WorkflowDefinition {
  id: string;
  name: string;
  description: string;
  icon: string;
  inputs: WorkflowInput[];
}

interface WorkflowSelectorProps {
  onSelect: (workflowId: string, config: Record<string, unknown>) => void;
}

type Phase = 'pick' | 'configure' | 'review';

const PREDEFINED_WORKFLOWS: WorkflowDefinition[] = [
  {
    id: 'research_pipeline',
    name: 'Research Pipeline',
    description: 'Search web sources, validate findings, and generate report',
    icon: '🔍',
    inputs: [
      { name: 'query', label: 'Research Topic', type: 'text', required: true },
      { name: 'max_sources', label: 'Max Sources', type: 'number', default: 5, required: false },
    ],
  },
  {
    id: 'batch_transform',
    name: 'Batch Transform',
    description: 'Convert multiple files between formats in parallel',
    icon: '🔄',
    inputs: [
      { name: 'files', label: 'Input Files', type: 'file', multiple: true, required: true },
      { name: 'target_format', label: 'Target Format', type: 'select', options: ['pdf', 'markdown', 'csv', 'docx'], required: true },
    ],
  },
  {
    id: 'data_validation',
    name: 'Data Validation',
    description: 'Validate data quality and schema compliance',
    icon: '✓',
    inputs: [
      { name: 'data_file', label: 'Data File', type: 'file', required: true },
      { name: 'schema', label: 'Schema (JSON)', type: 'textarea', required: false },
    ],
  },
  {
    id: 'team_discussion',
    name: 'Team Discussion',
    description: 'Multi-agent discussion until consensus reached',
    icon: '💬',
    inputs: [
      { name: 'topic', label: 'Discussion Topic', type: 'text', required: true },
      { name: 'participants', label: 'Participants', type: 'multiselect', options: ['researcher', 'analyst', 'critic'], required: false },
    ],
  },
];

export const WorkflowSelector: React.FC<WorkflowSelectorProps> = ({ onSelect }) => {
  const [selectedWorkflow, setSelectedWorkflow] = useState<WorkflowDefinition | null>(null);
  const [config, setConfig] = useState<Record<string, unknown>>({});
  const [customMode, setCustomMode] = useState(false);
  const [phase, setPhase] = useState<Phase>('pick');
  const [userGoal, setUserGoal] = useState('');
  const [customJsonText, setCustomJsonText] = useState('');
  const [customJsonError, setCustomJsonError] = useState<string | null>(null);

  const handleInputChange = (name: string, value: unknown) => {
    setConfig((prev) => ({ ...prev, [name]: value }));
  };

  const buildPayload = (): Record<string, unknown> => {
    const base = { ...config };
    const g = userGoal.trim();
    if (g) base.user_goal = g;
    return base;
  };

  const canProceedPredefined = selectedWorkflow
    ? !selectedWorkflow.inputs.some((i) => i.required && (config[i.name] === undefined || config[i.name] === ''))
    : false;

  const parsedCustom = useMemo(() => {
    try {
      return JSON.parse(customJsonText) as Record<string, unknown>;
    } catch {
      return null;
    }
  }, [customJsonText]);

  const renderInput = (input: WorkflowInput) => {
    const value = (config[input.name] as string) || '';

    if (input.type === 'select' && input.options) {
      return (
        <select
          value={value}
          onChange={(e) => handleInputChange(input.name, e.target.value)}
        >
          <option value="">Select...</option>
          {input.options.map((opt) => (
            <option key={opt} value={opt}>{opt}</option>
          ))}
        </select>
      );
    }

    if (input.type === 'textarea') {
      return (
        <textarea
          value={value}
          onChange={(e) => handleInputChange(input.name, e.target.value)}
          rows={4}
        />
      );
    }

    return (
      <input
        type={input.type === 'number' ? 'number' : 'text'}
        value={value}
        placeholder={input.default?.toString()}
        onChange={(e) => handleInputChange(input.name, e.target.value)}
      />
    );
  };

  const goReviewCustom = () => {
    setCustomJsonError(null);
    if (!parsedCustom || typeof parsedCustom !== 'object') {
      setCustomJsonError('Invalid JSON. Fix syntax before continuing.');
      return;
    }
    if (!parsedCustom.workflow_id) {
      setCustomJsonError('JSON must include workflow_id.');
      return;
    }
    const next = { ...parsedCustom } as Record<string, unknown>;
    const g = userGoal.trim();
    if (g) next.user_goal = g;
    setConfig(next);
    setPhase('review');
  };

  const confirmRun = () => {
    if (customMode) {
      const id = String(config.workflow_id ?? 'custom');
      onSelect(id, buildPayload());
      return;
    }
    if (selectedWorkflow) {
      onSelect(selectedWorkflow.id, buildPayload());
    }
  };

  const resetCustomMode = (checked: boolean) => {
    setCustomMode(checked);
    setPhase(checked ? 'configure' : 'pick');
    setSelectedWorkflow(null);
    setConfig({});
    setUserGoal('');
    setCustomJsonText('');
    setCustomJsonError(null);
  };

  const renderNaturalLanguageBlock = () => (
    <div className="workflow-nl-block input-field">
      <label>
        Describe your goal <span className="workflow-nl-hint">(optional — natural language; voice in composer below)</span>
      </label>
      <textarea
        className="workflow-nl-textarea"
        rows={3}
        placeholder="e.g. Summarize last week’s notes into a one-page brief for my manager…"
        value={userGoal}
        onChange={(e) => setUserGoal(e.target.value)}
      />
    </div>
  );

  const renderReviewPredefined = () => {
    if (!selectedWorkflow) return null;
    return (
      <div className="config-panel workflow-review-panel">
        <h4>Review & confirm</h4>
        <p className="workflow-review-lead">
          Claude-style <strong>plan check</strong> — confirm inputs before the runtime starts.
        </p>
        <ul className="workflow-review-list">
          <li><span className="label">Workflow</span> {selectedWorkflow.name} <code>({selectedWorkflow.id})</code></li>
          {userGoal.trim() && (
            <li><span className="label">Your goal</span> {userGoal.trim()}</li>
          )}
          {selectedWorkflow.inputs.map((i) => (
            <li key={i.name}>
              <span className="label">{i.label}</span>{' '}
              <code>{config[i.name] === undefined || config[i.name] === '' ? '—' : String(config[i.name])}</code>
            </li>
          ))}
        </ul>
        <div className="workflow-review-actions">
          <button type="button" className="btn-secondary" onClick={() => setPhase('configure')}>
            ← Back
          </button>
          <button type="button" className="start-btn" onClick={confirmRun}>
            Confirm & run
          </button>
        </div>
      </div>
    );
  };

  const renderReviewCustom = () => (
    <div className="config-panel workflow-review-panel">
      <h4>Review custom workflow</h4>
      <pre className="workflow-review-pre">{JSON.stringify(buildPayload(), null, 2)}</pre>
      <div className="workflow-review-actions">
        <button type="button" className="btn-secondary" onClick={() => setPhase('configure')}>
          ← Back
        </button>
        <button
          type="button"
          className="start-btn"
          onClick={confirmRun}
          disabled={!config.workflow_id}
        >
          Confirm & run
        </button>
      </div>
    </div>
  );

  return (
    <div className="workflow-selector">
      <div className="selector-header">
        <h3>Workflow</h3>
        <label className="mode-toggle">
          <input
            type="checkbox"
            checked={customMode}
            onChange={(e) => resetCustomMode(e.target.checked)}
          />
          Custom JSON
        </label>
      </div>

      {customMode ? (
        <>
          {phase === 'configure' && (
            <div className="custom-mode">
              {renderNaturalLanguageBlock()}
              <label className="input-field">
                <span style={{ display: 'block', marginBottom: 6, fontSize: 12, color: 'var(--muted)' }}>
                  Workflow JSON
                </span>
                <textarea
                  placeholder='{ "workflow_id": "...", "input_data": { ... } }'
                  rows={12}
                  value={customJsonText}
                  onChange={(e) => setCustomJsonText(e.target.value)}
                />
              </label>
              {customJsonError && <p className="workflow-json-error">{customJsonError}</p>}
              <button type="button" onClick={goReviewCustom}>
                Review before run
              </button>
            </div>
          )}
          {phase === 'review' && renderReviewCustom()}
        </>
      ) : (
        <>
          {phase === 'pick' && (
            <div className="workflow-grid">
              {PREDEFINED_WORKFLOWS.map((workflow) => (
                <div
                  key={workflow.id}
                  role="button"
                  tabIndex={0}
                  className={`workflow-card ${selectedWorkflow?.id === workflow.id ? 'selected' : ''}`}
                  onClick={() => {
                    setSelectedWorkflow(workflow);
                    setConfig({});
                    setPhase('configure');
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      setSelectedWorkflow(workflow);
                      setConfig({});
                      setPhase('configure');
                    }
                  }}
                >
                  <div className="workflow-icon">{workflow.icon}</div>
                  <h4>{workflow.name}</h4>
                  <p>{workflow.description}</p>
                </div>
              ))}
            </div>
          )}

          {phase === 'configure' && selectedWorkflow && (
            <div className="config-panel">
              <button
                type="button"
                className="btn-secondary workflow-back-btn"
                onClick={() => {
                  setPhase('pick');
                  setSelectedWorkflow(null);
                  setConfig({});
                }}
              >
                ← Choose another template
              </button>
              <h4>Configure: {selectedWorkflow.name}</h4>
              {renderNaturalLanguageBlock()}
              {selectedWorkflow.inputs.map((input) => (
                <div key={input.name} className="input-field">
                  <label>
                    {input.label}
                    {input.required && <span className="required">*</span>}
                  </label>
                  {renderInput(input)}
                </div>
              ))}
              <button
                type="button"
                className="start-btn"
                onClick={() => setPhase('review')}
                disabled={!canProceedPredefined}
              >
                Review plan
              </button>
            </div>
          )}

          {phase === 'review' && renderReviewPredefined()}
        </>
      )}
    </div>
  );
};
