import React, { createContext, useContext, useState } from 'react';

interface LayoutContextType {
  isAgentStreamOpen: boolean;
  toggleAgentStream: () => void;
  setAgentStreamOpen: (isOpen: boolean) => void;
}

const LayoutContext = createContext<LayoutContextType | undefined>(undefined);

export function LayoutProvider({ children }: { children: React.ReactNode }) {
  const [isAgentStreamOpen, setAgentStreamOpen] = useState(false);

  const toggleAgentStream = () => setAgentStreamOpen(prev => !prev);

  return (
    <LayoutContext.Provider value={{ isAgentStreamOpen, toggleAgentStream, setAgentStreamOpen }}>
      {children}
    </LayoutContext.Provider>
  );
}

export function useLayout() {
  const context = useContext(LayoutContext);
  if (context === undefined) {
    throw new Error('useLayout must be used within a LayoutProvider');
  }
  return context;
}
