import React from 'react';
import { Calendar, Download, Terminal, CheckCircle2 } from 'lucide-react';

export default function App() {
  return (
    <div className="min-h-screen bg-stone-50 text-stone-900 flex flex-col items-center justify-center p-6 font-sans">
      <div className="max-w-xl w-full bg-white rounded-2xl border border-stone-200 shadow-sm p-6 sm:p-8 space-y-6">
        <div className="flex items-center gap-3">
          <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl text-amber-700">
            <Calendar className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-stone-900">Triangle Kids Events Scraper</h1>
            <p className="text-xs text-stone-500">
              Barebone Python script generating Google Calendar readable .ics files
            </p>
          </div>
        </div>

        <div className="space-y-2">
          <div className="flex items-center gap-2 text-xs font-medium text-stone-700">
            <Terminal className="w-4 h-4 text-stone-500" />
            <span>Run Scraper Locally</span>
          </div>
          <div className="bg-stone-900 text-stone-100 p-3.5 rounded-xl font-mono text-xs overflow-x-auto">
            <code>python3 sync_events.py kids_events.ics</code>
          </div>
          <p className="text-[11px] text-stone-500">
            Uses Python standard library only (zero external pip packages required).
          </p>
        </div>

        <div className="pt-2 border-t border-stone-100 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-xs text-emerald-700 font-medium">
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
            <span>RFC 5545 iCalendar format</span>
          </div>

          <a
            href="/kids_events.ics"
            download="kids_events.ics"
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-4 py-2 bg-stone-900 hover:bg-stone-800 text-white rounded-xl text-xs font-medium transition-colors shadow-xs"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Download kids_events.ics</span>
          </a>
        </div>
      </div>
    </div>
  );
}
