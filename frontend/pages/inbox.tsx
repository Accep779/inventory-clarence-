import React from 'react';
import { AppShell } from '@/components/layout/AppShell';
import { ThreePaneLayout } from '@/components/inbox/ThreePaneLayout';
import { ErrorBoundary } from '@/components/ui/ErrorBoundary';

export default function DecisionInbox() {
  return (
    <AppShell title="Inbox">
       <ErrorBoundary>
        <ThreePaneLayout />
       </ErrorBoundary>
    </AppShell>
  );
}
