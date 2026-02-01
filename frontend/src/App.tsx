import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom';
import { AppProvider } from './contexts/AppContext';
import { SessionList } from './components/SessionList';
import { Chat } from './components/Chat';
import { Approvals } from './pages/Approvals';
import { KnowledgeGraph } from './pages/KnowledgeGraph';
import './App.css';

function AppContent() {
  const location = useLocation();
  const isChatPage = location.pathname === '/';

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-content">
          <div>
            <h1>🤖 Delivery Intelligence Assistant</h1>
            <p className="subtitle">AI-powered insights from Jira & Confluence</p>
          </div>
          <nav>
            <Link 
              to="/" 
              className={isChatPage ? 'active' : ''}
              title="Chat Interface"
            >
              💬 Chat
            </Link>
            <Link 
              to="/approvals" 
              className={location.pathname === '/approvals' ? 'active' : ''}
              title="View Approval Queue"
            >
              🔐 Approvals
            </Link>
            <Link 
              to="/graph" 
              className={location.pathname === '/graph' ? 'active' : ''}
              title="View Knowledge Graph"
            >
              🕸️ Knowledge Graph
            </Link>
          </nav>
        </div>
      </header>

      <div className="main-content">
        <Routes>
          <Route path="/" element={
            <>
              <SessionList />
              <Chat />
            </>
          } />
          <Route path="/approvals" element={<Approvals />} />
          <Route path="/graph" element={<KnowledgeGraph />} />
        </Routes>
      </div>
    </div>
  );
}

function App() {
  return (
    <AppProvider>
      <BrowserRouter>
        <AppContent />
      </BrowserRouter>
    </AppProvider>
  );
}

export default App;
