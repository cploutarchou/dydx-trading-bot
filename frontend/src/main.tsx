import React from 'react';
import ReactDOM from 'react-dom/client';
import { App } from './App';
import './index.css';
import { perfMark } from './utils/perf';

const rootElement = document.getElementById('root');

if (rootElement) {
  perfMark('boot:start');

  const app = <App />;

  ReactDOM.createRoot(rootElement).render(<React.StrictMode>{app}</React.StrictMode>);
} else {
  console.error('❌ main.tsx: Root element not found! Check index.html');
}
