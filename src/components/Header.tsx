import React from 'react';
import { Calendar, ShieldCheck, Clock } from 'lucide-react';
import { SyncStatus } from '../types';

interface HeaderProps {
  status: SyncStatus | null;
  isRunning: boolean;
  onTriggerSync: () => void;
  onDownloadIcs: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  status,
  isRunning,
  onTriggerSync,
  onDownloadIcs,
}) => {
  return (
    <header className="border-b border-stone-200 bg-white/80 backdrop-blur-md sticky top-0 z-30">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-600 shadow-xs">
              <Calendar className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl font-semibold text-stone-900 tracking-tight">
                  Triangle Kids Events Sync
                </h1>
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                  <ShieldCheck className="w-3 h-3" />
                  RFC 5545 Valid
                </span>
              </div>
              <p className="text-xs text-stone-500 mt-0.5">
                Automated iCalendar sync for free & cheap kids events across Raleigh, Durham & Chapel Hill
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            <button
              id="header-run-sync-btn"
              onClick={onTriggerSync}
              disabled={isRunning}
              className={`inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors shadow-xs ${
                isRunning
                  ? 'bg-stone-100 text-stone-400 cursor-not-allowed border border-stone-200'
                  : 'bg-amber-600 hover:bg-amber-700 text-white active:bg-amber-800'
              }`}
            >
              <Clock className={`w-4 h-4 ${isRunning ? 'animate-spin' : ''}`} />
              {isRunning ? 'Testing Scraper...' : 'Run Scraper Test'}
            </button>

            <button
              id="header-download-ics-btn"
              onClick={onDownloadIcs}
              className="inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-white hover:bg-stone-50 text-stone-700 border border-stone-300 transition-colors shadow-xs active:bg-stone-100"
            >
              <Calendar className="w-4 h-4 text-stone-500" />
              Download .ics
            </button>
          </div>
        </div>
      </div>
    </header>
  );
};
