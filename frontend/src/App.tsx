import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from './context/AuthContext';
import { Header } from './components/Header';
import { ClickEffect } from './components/ClickEffect';
import { HeroPage } from './pages/HeroPage';
import { ClientPortalPage } from './pages/ClientPortalPage';
import { CaseViewPage } from './pages/CaseViewPage';
import { ArenaPage } from './pages/ArenaPage';
import { ReportsPage } from './pages/ReportsPage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      staleTime: 30000,
    },
  },
});

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <div className="min-h-screen flex flex-col font-sans bg-[#FAF8F5] text-stone-900 selection:bg-stone-900 selection:text-white">
            <ClickEffect />
            <Header />
            <div className="flex-1">
              <Routes>
                {/* Marketing & Showcase Dual-Audience Hero Portal */}
                <Route path="/" element={<HeroPage />} />

                {/* Client / Policyholder Self-Service Portal */}
                <Route path="/portal" element={<ClientPortalPage />} />

                {/* Adjuster Inbox & Case Forensics Workspace */}
                <Route path="/inbox" element={<CaseViewPage />} />
                <Route path="/cases/:caseId" element={<CaseViewPage />} />

                {/* Red-Team Generative Arena */}
                <Route path="/arena" element={<ArenaPage />} />

                {/* Evaluation & Latency Reports */}
                <Route path="/reports" element={<ReportsPage />} />

                {/* Catch-all redirect */}
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </div>
          </div>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}

export default App;
