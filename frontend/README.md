# Sophon frontend

React, TypeScript, and Vite. Chat, workflows, and runtime status against the local API.

## Quick Start

```bash
npm install
npm run dev
```

## Co-work Components

### Basic Usage

```tsx
import { StatusMonitor, useWorkflow, useSSE } from './components';

function App() {
  const { workflowState, run, pause, resume, stop } = useWorkflow();
  const { isConnected } = useSSE(workflowState?.instance_id);

  if (!workflowState) {
    return <button onClick={() => run({ 
      workflow_id: 'research', 
      input_data: { query: 'test' } 
    })}>Start Workflow</button>;
  }

  return (
    <StatusMonitor 
      workflowState={workflowState}
      onPause={pause}
      onResume={resume}
      onStop={stop}
    />
  );
}
```

### Available Components

- **StatusMonitor** - Main dashboard (workflow status, steps, batch progress, artifacts)
- **AgentPanel** - List of active agents
- **MessageStream** - Real-time message feed
- **RuntimeControls** - Pause/Resume/Stop buttons

### Hooks

- `useWorkflow()` - Manage workflow lifecycle
- `useSSE(instanceId)` - Real-time updates via Server-Sent Events

## Workflow Types

- `research` - Search → Crawl → Analyze
- `transform` - Format conversion (CSV/PDF/Markdown/Word)
- `validate` - Data quality checking
- `discuss` - Multi-agent discussion until consensus

## API

Backend port defaults to `DEFAULT_API_PORT` in the repo `config/` package (override with `PORT`). The Vite dev proxy uses `VITE_SOPHON_API_PORT` or `PORT` if set, with the same default as the `config/` package.

Key endpoints:
- `POST /api/v1/workflows/{id}/run` - Start workflow
- `GET /api/v1/instances/{id}/stream` - SSE real-time updates

## Workspace Protocol

- Local files can be attached in batches and uploaded to the user workspace `docs/` directory by default.
- Workflow results expose artifact paths through the shared protocol so the UI can render/download multi-file outputs without hardcoding file types.
- Workspace listings hide system files and database files; the UI only shows user-visible files.

---

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the ESLint configuration

If you are developing a production application, we recommend updating the configuration to enable type-aware lint rules:

```js
export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...

      // Remove tseslint.configs.recommended and replace with this
      tseslint.configs.recommendedTypeChecked,
      // Alternatively, use this for stricter rules
      tseslint.configs.strictTypeChecked,
      // Optionally, add this for stylistic rules
      tseslint.configs.stylisticTypeChecked,

      // Other configs...
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])
```

You can also install [eslint-plugin-react-x](https://github.com/Rel1cx/eslint-react/tree/main/packages/plugins/eslint-plugin-react-x) and [eslint-plugin-react-dom](https://github.com/Rel1cx/eslint-react/tree/main/packages/plugins/eslint-plugin-react-dom) for React-specific lint rules:

```js
// eslint.config.js
import reactX from 'eslint-plugin-react-x'
import reactDom from 'eslint-plugin-react-dom'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...
      // Enable lint rules for React
      reactX.configs['recommended-typescript'],
      // Enable lint rules for React DOM
      reactDom.configs.recommended,
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])
```
