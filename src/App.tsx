import React, { useState, useEffect } from 'react';
import { Header } from './components/Header';
import { SyncControlPanel } from './components/SyncControlPanel';
import { EventList } from './components/EventList';
import { WorkflowViewer } from './components/WorkflowViewer';
import { KidEvent, SyncStatus, SyncResult } from './types';
import { Calendar, Code2, AlertCircle } from 'lucide-react';

export default function App() {
  const [status, setStatus] = useState<SyncStatus | null>(null);
  const [events, setEvents] = useState<KidEvent[]>([]);
  const [isLoadingEvents, setIsLoadingEvents] = useState(true);
  const [isRunningSync, setIsRunningSync] = useState(false);
  const [lastRunResult, setLastRunResult] = useState<SyncResult | null>(null);
  const [activeTab, setActiveTab] = useState<'events' | 'code'>('events');
  const [alertMessage, setAlertMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const fetchStatus = async () => {
    try {
      const res = await fetch('/api/status');
      if (res.ok) {
        const data = await res.json();
        setStatus(data);
      }
    } catch (err) {
      console.error('Error fetching status:', err);
    }
  };

  const fetchEvents = async () => {
    setIsLoadingEvents(true);
    try {
      const res = await fetch('/api/events');
      if (res.ok) {
        const data = await res.json();
        setEvents(data.events || []);
      }
    } catch (err) {
      console.error('Error fetching events:', err);
    } finally {
      setIsLoadingEvents(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    fetchEvents();
  }, []);

  const handleTriggerSync = async () => {
    setIsRunningSync(true);
    setAlertMessage(null);
    try {
      const res = await fetch('/api/trigger-sync', { method: 'POST' });
      const data = await res.json();
      setLastRunResult(data);

      if (data.success) {
        setAlertMessage({
          type: 'success',
          text: `Scraper executed successfully in ${(data.durationMs / 1000).toFixed(2)}s! Generated calendar with ${data.eventCount} kid events.`,
        });
        await fetchStatus();
        await fetchEvents();
      } else {
        setAlertMessage({
          type: 'error',
          text: `Sync error: ${data.error || 'Failed to execute scraper'}`,
        });
      }
    } catch (err: any) {
      setAlertMessage({
        type: 'error',
        text: `Network error: ${err.message || 'Unable to contact server'}`,
      });
    } finally {
      setIsRunningSync(false);
    }
  };

  const handleDownloadIcs = () => {
    const link = document.createElement('a');
    link.href = '/kids_events.ics';
    link.setAttribute('download', 'kids_events.ics');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="min-h-screen bg-stone-100/60 text-stone-900 flex flex-col font-sans selection:bg-amber-500/20 selection:text-amber-900">
      <Header
        status={status}
        isRunning={isRunningSync}
        onTriggerSync={handleTriggerSync}
        onDownloadIcs={handleDownloadIcs}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        {alertMessage && (
          <div
            className={`p-4 rounded-xl text-xs font-medium border flex items-center justify-between gap-3 shadow-xs ${
              alertMessage.type === 'success'
                ? 'bg-emerald-50 text-emerald-900 border-emerald-200'
                : 'bg-red-50 text-red-900 border-red-200'
            }`}
          >
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{alertMessage.text}</span>
            </div>
            <button
              onClick={() => setAlertMessage(null)}
              className="text-stone-400 hover:text-stone-700 underline text-[11px]"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Dashboard control & metrics */}
        <SyncControlPanel
          status={status}
          lastRunResult={lastRunResult}
          isRunning={isRunningSync}
          onTriggerSync={handleTriggerSync}
          onDownloadIcs={handleDownloadIcs}
        />

        {/* Section Tabs */}
        <div className="flex items-center justify-between border-b border-stone-200 pb-3">
          <div className="flex items-center gap-2">
            <button
              id="view-events-tab"
              onClick={() => setActiveTab('events')}
              className={`inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                activeTab === 'events'
                  ? 'bg-stone-900 text-white shadow-xs'
                  : 'bg-white text-stone-600 hover:text-stone-900 border border-stone-200'
              }`}
            >
              <Calendar className="w-3.5 h-3.5" />
              Upcoming Events ({events.length})
            </button>

            <button
              id="view-code-tab"
              onClick={() => setActiveTab('code')}
              className={`inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                activeTab === 'code'
                  ? 'bg-stone-900 text-white shadow-xs'
                  : 'bg-white text-stone-600 hover:text-stone-900 border border-stone-200'
              }`}
            >
              <Code2 className="w-3.5 h-3.5" />
              Script & GitHub Workflow
            </button>
          </div>
        </div>

        {/* Tab content */}
        {activeTab === 'events' ? (
          <EventList events={events} isLoading={isLoadingEvents} />
        ) : (
          <WorkflowViewer />
        )}
      </main>

      <footer className="border-t border-stone-200 bg-white py-6 mt-12 text-center text-xs text-stone-500">
        <div className="max-w-7xl mx-auto px-4">
          <p>
            Triangle on the Cheap Kids Events Calendar Sync &bull; Automated via Python &amp; GitHub Actions &bull; RFC 5545 iCalendar standard
          </p>
        </div>
      </footer>
    </div>
  );
}
