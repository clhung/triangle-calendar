import React, { useState, useMemo } from 'react';
import { Search, MapPin, Clock, DollarSign, ExternalLink, Calendar, Filter } from 'lucide-react';
import { KidEvent } from '../types';

interface EventListProps {
  events: KidEvent[];
  isLoading: boolean;
}

export const EventList: React.FC<EventListProps> = ({ events, isLoading }) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedTown, setSelectedTown] = useState('all');
  const [freeOnly, setFreeOnly] = useState(false);

  // Extract unique towns/cities from locations
  const towns = useMemo(() => {
    const list = new Set<string>();
    const known = ['Raleigh', 'Durham', 'Chapel Hill', 'Cary', 'Apex', 'Wake Forest', 'Hillsborough', 'Carrboro', 'Morrisville', 'Holly Springs', 'Garner'];
    events.forEach((ev) => {
      known.forEach((k) => {
        if (ev.location.toLowerCase().includes(k.toLowerCase())) {
          list.add(k);
        }
      });
    });
    return Array.from(list).sort();
  }, [events]);

  const filteredEvents = useMemo(() => {
    return events.filter((ev) => {
      const q = searchQuery.toLowerCase().trim();
      const matchesQuery =
        !q ||
        ev.title.toLowerCase().includes(q) ||
        ev.location.toLowerCase().includes(q) ||
        ev.cost.toLowerCase().includes(q);

      const matchesTown =
        selectedTown === 'all' ||
        ev.location.toLowerCase().includes(selectedTown.toLowerCase());

      const matchesFree = !freeOnly || ev.cost.toLowerCase().includes('free') || ev.cost === '$0' || ev.title.toLowerCase().includes('free');

      return matchesQuery && matchesTown && matchesFree;
    });
  }, [events, searchQuery, selectedTown, freeOnly]);

  const formatEventDate = (dateStr: string) => {
    try {
      const [y, m, d] = dateStr.split('-').map(Number);
      const dt = new Date(y, m - 1, d);
      return dt.toLocaleDateString('en-US', {
        weekday: 'short',
        month: 'short',
        day: 'numeric',
      });
    } catch {
      return dateStr;
    }
  };

  return (
    <div className="bg-white rounded-2xl border border-stone-200 shadow-xs overflow-hidden">
      {/* Search and Filters Header */}
      <div className="p-4 sm:p-5 border-b border-stone-200 bg-stone-50/50">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          <div>
            <h3 className="text-base font-semibold text-stone-900">
              Scraped Kids Events Feed
            </h3>
            <p className="text-xs text-stone-500 mt-0.5">
              Showing {filteredEvents.length} of {events.length} parsed events from Triangle on the Cheap
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div className="relative min-w-[200px] flex-1 sm:flex-initial">
              <Search className="w-4 h-4 text-stone-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                id="event-search-input"
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search event, park, venue..."
                className="w-full pl-9 pr-3 py-1.5 text-xs bg-white border border-stone-300 rounded-lg text-stone-800 placeholder-stone-400 focus:outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 transition-colors"
              />
            </div>

            <select
              id="event-town-filter"
              value={selectedTown}
              onChange={(e) => setSelectedTown(e.target.value)}
              className="py-1.5 px-3 text-xs bg-white border border-stone-300 rounded-lg text-stone-700 focus:outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500"
            >
              <option value="all">All Locations</option>
              {towns.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>

            <button
              id="event-free-toggle"
              type="button"
              onClick={() => setFreeOnly(!freeOnly)}
              className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors flex items-center gap-1.5 ${
                freeOnly
                  ? 'bg-emerald-600 text-white border-emerald-600'
                  : 'bg-white text-stone-600 border-stone-300 hover:bg-stone-50'
              }`}
            >
              <DollarSign className="w-3.5 h-3.5" />
              Free Events Only
            </button>
          </div>
        </div>
      </div>

      {/* Events listing */}
      <div className="divide-y divide-stone-100 max-h-[640px] overflow-y-auto">
        {isLoading ? (
          <div className="p-12 text-center text-sm text-stone-500">
            Loading scraped events...
          </div>
        ) : filteredEvents.length === 0 ? (
          <div className="p-12 text-center">
            <Calendar className="w-8 h-8 text-stone-300 mx-auto mb-2" />
            <p className="text-sm font-medium text-stone-700">No events matched your criteria</p>
            <p className="text-xs text-stone-400 mt-1">Try clearing filters or search keywords.</p>
          </div>
        ) : (
          filteredEvents.map((event) => (
            <div
              key={event.uid}
              className="p-4 sm:p-5 hover:bg-stone-50/70 transition-colors flex flex-col sm:flex-row sm:items-start justify-between gap-3"
            >
              <div className="space-y-1.5 flex-1 min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold bg-amber-50 text-amber-800 border border-amber-200">
                    {formatEventDate(event.date)}
                  </span>
                  {event.cost && (
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium ${
                        event.cost.toLowerCase().includes('free')
                          ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                          : 'bg-stone-100 text-stone-700 border border-stone-200'
                      }`}
                    >
                      {event.cost}
                    </span>
                  )}
                </div>

                <h4 className="text-sm font-semibold text-stone-900 leading-snug">
                  {event.title}
                </h4>

                <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-stone-500 pt-0.5">
                  {event.time_str && (
                    <div className="flex items-center gap-1">
                      <Clock className="w-3.5 h-3.5 text-stone-400 shrink-0" />
                      <span>{event.time_str}</span>
                    </div>
                  )}
                  {event.location && (
                    <div className="flex items-center gap-1">
                      <MapPin className="w-3.5 h-3.5 text-stone-400 shrink-0" />
                      <span className="truncate max-w-xs">{event.location}</span>
                    </div>
                  )}
                </div>
              </div>

              {event.url && (
                <a
                  href={event.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium text-stone-600 hover:text-stone-900 bg-stone-100 hover:bg-stone-200 transition-colors shrink-0 self-start sm:self-center"
                >
                  <span>Event Info</span>
                  <ExternalLink className="w-3 h-3" />
                </a>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
};
