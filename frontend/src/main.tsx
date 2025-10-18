import React from 'react'
import ReactDOM from 'react-dom/client'
import { App } from './App'
import './index.css'

console.log('🔧 main.tsx: Starting app initialization')
const rootElement = document.getElementById('root')
console.log('🔧 main.tsx: Root element found:', rootElement ? '✅ Yes' : '❌ No')

if (rootElement) {
    console.log('🔧 main.tsx: Creating React root and rendering App')
    ReactDOM.createRoot(rootElement).render(
        <React.StrictMode>
            <App />
        </React.StrictMode>,
    )
    console.log('🔧 main.tsx: App rendered successfully')
} else {
    console.error('❌ main.tsx: Root element not found! Check index.html')
}
