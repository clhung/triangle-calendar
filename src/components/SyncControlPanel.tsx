import React, { useState } from 'react';
import { Play, Copy, Check, Terminal, ExternalLink, Shield, KeyRound, CalendarCheck, Sparkles } from 'lucide-react';
import { SyncStatus, SyncResult } from '../types';

interface SyncControlPanelProps {
  status: SyncStatus | null;
  lastRunResult: SyncResult | null;
  isRunning: boolean;
  onTriggerSync: () => void;
  onDownloadIcs: () => void;
}

export const SyncControlPanel: React.FC<SyncControlPanelProps> = ({
  status,
  lastRunResult,
  isRunning,
  onTriggerSync,
  onDownloadIcs,
}) => {
  const [copiedFeed, setCopiedFeed] = useState(false);
  const [showLogs, setShowLogs] = useState(false);

  const appOrigin = typeof window !== 'undefined' ? window.location.origin : '';
  const icsUrl = `${appOrigin}/kids_events.ics`;
  const webcalUrl = icsUrl.replace(/^https?:/, 'webcal:');

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedFeed(true);
    setTimeout(() => setCopiedFeed(false), 2000);
  };

  const formatFileSize = (bytes: number) => {
    if (!bytes) return '0 KB';
    return `${(bytes / 1024).toFixed(1)} KB`;
  };

  const formatDate = (isoString: string | null) => {
    if (!isoString) return 'Not run yet';
    try {
      const d = new Date(isoString);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', month: 'short', day: 'numeric' });
    } catch {
      return isoString;
    }
  };

  return (
    <div className="space-y-4">
      {/* Top metrics bar */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="bg-white p-4 rounded-xl border border-stone-200 shadow-xs">
          <div className="text-xs font-medium text-stone-500">Extracted Events</div>
          <div className="text-2xl font-semibold text-stone-900 mt-1 flex items-baseline gap-1.5">
            {status?.calendar.eventCount || 0}
            <span className="text-xs font-normal text-stone-400">events</span>
          </div>
          <div className="text-xs text-emerald-600 font-medium mt-1 flex items-center gap-1">
            <CalendarCheck className="w-3.5 h-3.5" />
            Next 30 Days
          </div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-stone-200 shadow-xs">
          <div className="text-xs font-medium text-stone-500">Calendar Size</div>
          <div className="text-2xl font-semibold text-stone-900 mt-1">
            {formatFileSize(status?.calendar.size || 0)}
          </div>
          <div className="text-xs text-stone-500 mt-1">
            RFC 5545 .ics file
          </div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-stone-200 shadow-xs">
          <div className="text-xs font-medium text-stone-500">Last Scraper Run</div>
          <div className="text-sm font-semibold text-stone-900 mt-2 truncate">
            {formatDate(status?.calendar.updatedAt || null)}
          </div>
          <div className="text-xs text-stone-500 mt-1">
            {status?.calendar.exists ? 'Updated on disk' : 'Pending initial run'}
          </div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-stone-200 shadow-xs">
          <div className="text-xs font-medium text-stone-500">GitHub Cron Sync</div>
          <div className="text-sm font-semibold text-stone-900 mt-2 flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
            Daily @ 06:00 UTC
          </div>
          <div className="text-xs text-stone-500 mt-1">
            .github/workflows/sync.yml
          </div>
        </div>
      </div>

      {/* Action and subscription card */}
      <div className="bg-stone-900 text-white rounded-2xl p-5 shadow-sm">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-amber-400" />
              <h2 className="text-base font-semibold text-white tracking-tight">
                Subscribe & Sync to Calendar Apps
              </h2>
            </div>
            <p className="text-xs text-stone-400 max-w-xl">
              Add this feed directly to Apple Calendar, Google Calendar, or Outlook to receive live event updates automatically.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              id="copy-feed-url-btn"
              onClick={() => copyToClipboard(icsUrl)}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-medium bg-stone-800 hover:bg-stone-700 text-stone-200 border border-stone-700 transition-colors"
            >
              {copiedFeed ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
              {copiedFeed ? 'Copied Feed URL!' : 'Copy Feed URL'}
            </button>

            <a
              id="subscribe-webcal-link"
              href={webcalUrl}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-medium bg-amber-500 hover:bg-amber-600 text-stone-950 font-semibold transition-colors"
            >
              <CalendarCheck className="w-3.5 h-3.5" />
              Subscribe in Calendar
            </a>

            <button
              id="toggle-logs-btn"
              onClick={() => setShowLogs(!showLogs)}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-medium bg-stone-800 hover:bg-stone-700 text-stone-300 border border-stone-700 transition-colors"
            >
              <Terminal className="w-3.5 h-3.5" />
              {showLogs ? 'Hide Scraper Logs' : 'View Logs'}
            </button>
          </div>
        </div>

        {/* Scraper Log Output */}
        {showLogs && (
          <div className="mt-4 pt-4 border-t border-stone-800">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-mono text-stone-400 flex items-center gap-1.5">
                <Terminal className="w-3.5 h-3.5" />
                Latest Scraper Terminal Output (sync_events.py)
              </span>
              <button
                onClick={onTriggerSync}
                disabled={isRunning}
                className="text-xs text-amber-400 hover:text-amber-300 disabled:opacity-50 font-medium"
              >
                {isRunning ? 'Running...' : 'Re-run Scraper'}
              </button>
            </div>
            <pre className="p-3 rounded-lg bg-black/60 border border-stone-800 font-mono text-xs text-emerald-400 overflow-x-auto max-h-56 leading-relaxed whitespace-pre-wrap">
              {lastRunResult?.stdout || 'No live logs captured yet. Click "Run Scraper Test" to execute.'}
              {lastRunResult?.stderr && (
                <span className="text-red-400 block mt-2">{lastRunResult.stderr}</span>
              )}
            </pre>
          </div>
        )}
      </div>

      {/* Security notice banner */}
      <div className="bg-emerald-50/70 border border-emerald-200 rounded-xl p-3.5 flex items-start gap-3 text-xs text-emerald-900">
        <Shield className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
        <div className="leading-relaxed">
          <span className="font-semibold">Security & Secrets Protection: </span>
          The scraper uses standard library requests without requiring third-party credentials. In the GitHub Actions workflow (<code className="bg-emerald-100/80 px-1 py-0.5 rounded font-mono text-[11px]">.github/workflows/sync.yml</code>), any sensitive parameters use encrypted GitHub Secrets (<code className="bg-emerald-100/80 px-1 py-0.5 rounded font-mono text-[11px]">{"${{ secrets.GITHUB_TOKEN }}"}</code>) and environment variables, keeping all credentials completely hidden.
        </div>
      </div>
    </div>
  );
};
