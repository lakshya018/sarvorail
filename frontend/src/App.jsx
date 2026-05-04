import React, { useState, useMemo, useEffect, useRef, useCallback } from 'react';
import {
  ArrowRightCircle,
  SlidersHorizontal,
  MapPin,
  Calendar,
  ArrowUpDown,
  Zap,
  Sunrise,
  Sunset,
  Train as TrainIcon,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { DayPicker } from 'react-day-picker';

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000/api/v1';

const getStationLabel = (code, namesMap) => {
  const name = namesMap[code];
  return name ? `${name} (${code})` : code;
};

function StationInput({ value, onChange, placeholder, onSelectName, stationNames = {} }) {
  const [inputDisplay, setInputDisplay] = useState(() => {
    const name = stationNames[value];
    return name ? `${name} (${value})` : (value || '');
  });
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [loading, setLoading] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [isFocused, setIsFocused] = useState(false);

  const debounceRef = useRef(null);
  const inputRef = useRef(null);
  const listRef = useRef(null);

  useEffect(() => {
    const name = stationNames[value];
    setInputDisplay(name ? `${name} (${value})` : (value || ''));
  }, [value]); // eslint-disable-line react-hooks/exhaustive-deps

  const fetchSuggestions = (q) => {
    clearTimeout(debounceRef.current);
    if (!q || q.length < 2) { setSuggestions([]); setShowSuggestions(false); return; }
    debounceRef.current = setTimeout(async () => {
      setLoading(true);
      try {
        const res = await fetch(`${API_BASE}/stations/search?query=${encodeURIComponent(q)}`);
        const data = await res.json();
        setSuggestions(data);
        setActiveIndex(-1);
        setShowSuggestions(data.length > 0);
      } catch { setSuggestions([]); }
      finally { setLoading(false); }
    }, 250);
  };

  const handleSelect = (station) => {
    setInputDisplay(`${station.station_name} (${station.station_code})`);
    onChange(station.station_code);
    onSelectName(station.station_code, station.station_name);
    setSuggestions([]);
    setShowSuggestions(false);
    setActiveIndex(-1);
  };

  const scrollActiveIntoView = (idx) => {
    listRef.current?.querySelector(`[data-idx="${idx}"]`)?.scrollIntoView({ block: 'nearest' });
  };

  const handleKeyDown = (e) => {
    if (!showSuggestions || !suggestions.length) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      const next = Math.min(activeIndex + 1, suggestions.length - 1);
      setActiveIndex(next); scrollActiveIntoView(next);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      const next = Math.max(activeIndex - 1, 0);
      setActiveIndex(next); scrollActiveIntoView(next);
    } else if (e.key === 'Enter' && activeIndex >= 0) {
      e.preventDefault(); handleSelect(suggestions[activeIndex]);
    } else if (e.key === 'Escape') {
      setShowSuggestions(false); setActiveIndex(-1);
    }
  };

  return (
    <div className="relative w-full">
      <div className={`relative bg-white/[0.04] border-[1.5px] rounded-[14px] transition-all duration-200 ${
        isFocused
          ? 'border-indigo-500/60 shadow-[0_0_0_4px_rgba(99,102,241,0.1)]'
          : 'border-white/[0.09]'
      }`}>
        <MapPin
          size={15}
          className={`absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none transition-colors duration-200 ${isFocused ? 'text-indigo-500' : 'text-gray-600'}`}
        />
        <input
          ref={inputRef}
          type="text"
          value={inputDisplay}
          onChange={(e) => { setInputDisplay(e.target.value); fetchSuggestions(e.target.value); }}
          onFocus={(e) => {
            setIsFocused(true);
            if (suggestions.length > 0) setShowSuggestions(true);
            setTimeout(() => e.target.select(), 0);
          }}
          onBlur={() => { setIsFocused(false); setTimeout(() => setShowSuggestions(false), 150); }}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          className="w-full h-10 bg-transparent border-none outline-none pl-8 pr-8 text-slate-100 text-xs font-semibold tracking-wide placeholder:text-gray-600"
        />

        {inputDisplay && (
          <button
            type="button"
            onMouseDown={(e) => {
              e.preventDefault();
              setInputDisplay(''); onChange('');
              setSuggestions([]); setShowSuggestions(false);
              inputRef.current?.focus();
            }}
            className="absolute right-2.5 top-1/2 -translate-y-1/2 w-5 h-5 bg-white/[0.08] border-none rounded-full flex items-center justify-center cursor-pointer text-gray-500"
          >
            <svg width="8" height="8" viewBox="0 0 8 8" fill="none">
              <path d="M1 1l6 6M7 1L1 7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
          </button>
        )}

        {loading && (
          <div className={`absolute top-1/2 -translate-y-1/2 w-[13px] h-[13px] border-2 border-indigo-500/20 border-t-indigo-500 rounded-full animate-spin ${inputDisplay ? 'right-[38px]' : 'right-3'}`} />
        )}
      </div>

      <AnimatePresence>
        {showSuggestions && suggestions.length > 0 && (
          <motion.div
            ref={listRef}
            initial={{ opacity: 0, y: -8, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.97 }}
            transition={{ duration: 0.13, ease: 'easeOut' }}
            className="absolute z-[200] w-full top-[calc(100%+6px)] bg-[rgba(10,12,24,0.98)] backdrop-blur-2xl border border-indigo-500/20 rounded-2xl shadow-[0_24px_60px_rgba(0,0,0,0.65),inset_0_0_0_1px_rgba(255,255,255,0.03)] overflow-hidden max-h-[300px] overflow-y-auto [scrollbar-width:thin] [scrollbar-color:rgba(99,102,241,0.25)_transparent]"
          >
            <div className="sticky top-0 z-10 px-3.5 py-2 bg-[rgba(10,12,24,0.98)] border-b border-white/[0.05] flex justify-between items-center">
              <span className="text-[9px] text-gray-600 font-black tracking-[0.12em] uppercase">{suggestions.length} stations</span>
              <span className="text-[9px] text-gray-800 font-bold tracking-[0.04em]">↑↓ · ↵ select · esc</span>
            </div>

            {suggestions.map((s, i) => {
              const isActive = i === activeIndex;
              return (
                <div
                  key={s.station_code}
                  data-idx={i}
                  onMouseDown={() => handleSelect(s)}
                  onMouseEnter={() => setActiveIndex(i)}
                  className={`flex items-center gap-3 px-3.5 py-2.5 cursor-pointer transition-colors duration-75 border-l-[3px] ${
                    isActive ? 'bg-indigo-500/10 border-l-indigo-500' : 'border-l-transparent'
                  } ${i < suggestions.length - 1 ? 'border-b border-b-white/[0.03]' : ''}`}
                >
                  <div className={`shrink-0 min-w-[42px] px-1.5 py-[3px] rounded-[6px] text-center text-[10px] font-black tracking-[0.04em] border ${
                    isActive ? 'bg-indigo-500/20 border-indigo-500/40 text-indigo-300' : 'bg-white/[0.05] border-white/[0.07] text-gray-500'
                  }`}>
                    {s.station_code}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className={`text-[13px] font-semibold truncate ${isActive ? 'text-slate-100' : 'text-slate-300'}`}>{s.station_name}</div>
                    <div className="text-[10px] text-gray-700 font-bold mt-px tracking-[0.04em] uppercase">{s.state}</div>
                  </div>
                </div>
              );
            })}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function DatePicker({ value, onChange }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  // Parse YYYY-MM-DD string to Date
  const selected = value ? new Date(value + 'T00:00:00') : undefined;

  const handleSelect = (day) => {
    if (!day) return;
    const yyyy = day.getFullYear();
    const mm = String(day.getMonth() + 1).padStart(2, '0');
    const dd = String(day.getDate()).padStart(2, '0');
    onChange(`${yyyy}-${mm}-${dd}`);
    setOpen(false);
  };

  // Close on outside click
  useEffect(() => {
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const display = selected
    ? selected.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
    : 'Select date';

  return (
    <div ref={ref} className="relative w-full">
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className={`w-full h-10 flex items-center gap-2 px-3 bg-white/[0.04] border-[1.5px] rounded-[14px] text-xs font-semibold transition-all duration-200 cursor-pointer ${
          open ? 'border-indigo-500/60 shadow-[0_0_0_4px_rgba(99,102,241,0.1)]' : 'border-white/[0.09]'
        } ${selected ? 'text-white' : 'text-gray-500'}`}
      >
        <Calendar size={14} className={open ? 'text-indigo-500' : 'text-gray-600'} />
        {display}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -6, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.97 }}
            transition={{ duration: 0.15, ease: 'easeOut' }}
            className="absolute z-[300] top-[calc(100%+6px)] left-0 bg-gray-950 border border-white/[0.1] rounded-2xl shadow-[0_24px_60px_rgba(0,0,0,0.7)] p-3"
          >
            <DayPicker
              mode="single"
              selected={selected}
              onSelect={handleSelect}
              disabled={{ before: new Date() }}
              startMonth={new Date()}
              endMonth={new Date(new Date().getFullYear() + 2, 11)}
              classNames={{
                root: 'text-xs w-[252px]',
                months: 'flex flex-col',
                month: 'space-y-2',
                month_caption: 'flex justify-between items-center px-1 pb-2 border-b border-white/[0.06]',
                caption_label: 'text-sm font-bold text-white',
                nav: 'flex items-center gap-1',
                button_previous: 'w-7 h-7 flex items-center justify-center rounded-lg bg-white/20 text-white hover:bg-indigo-500/50 hover:text-white transition-colors cursor-pointer disabled:bg-white/[0.04] disabled:text-gray-600 disabled:cursor-not-allowed',
                button_next: 'w-7 h-7 flex items-center justify-center rounded-lg bg-white/20 text-white hover:bg-indigo-500/50 hover:text-white transition-colors cursor-pointer disabled:bg-white/[0.04] disabled:text-gray-600 disabled:cursor-not-allowed',
                month_grid: 'w-full border-collapse mt-2',
                weekdays: 'flex',
                weekday: 'w-9 text-center text-[10px] font-bold text-gray-600 py-1',
                week: 'flex mt-1',
                day: 'w-9 h-9 p-0',
                day_button: 'w-full h-full flex items-center justify-center rounded-lg text-xs font-semibold text-gray-300 hover:bg-white/[0.08] hover:text-white transition-colors cursor-pointer',
                selected: '[&>button]:!bg-indigo-500 [&>button]:!text-white [&>button]:shadow-[0_0_12px_rgba(99,102,241,0.4)]',
                today: '[&>button]:text-indigo-400 [&>button]:font-black',
                disabled: '[&>button]:!text-gray-700 [&>button]:!cursor-not-allowed [&>button]:hover:!bg-transparent',
                outside: '[&>button]:!text-gray-700',
              }}
            />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function App() {
  const [source, setSource] = useState('');
  const [dest, setDest] = useState('');
  const [date, setDate] = useState('2026-05-04');
  const [hasSearched, setHasSearched] = useState(false);
  const [nearby, setNearby] = useState(0);
  const [maxConn, setMaxConn] = useState(2);
  const [minLayover, setMinLayover] = useState(30);
  const [quota, setQuota] = useState('GN');
  const [showFilters, setShowFilters] = useState(false);
  const [sortBy, setSortBy] = useState('duration');

  const [loading, setLoading] = useState(false);
  const [routes, setRoutes] = useState([]);
  const [logs, setLogs] = useState([]);
  const [error, setError] = useState(null);
  const [stationNames, setStationNames] = useState({});

  const updateStationName = (code, name) => setStationNames(prev => ({ ...prev, [code]: name }));

  const handleSwap = () => { setSource(dest); setDest(source); };

  const addLog = (msg) => setLogs(prev => [`> ${msg}`, ...prev].slice(0, 5));

  const handleSearch = async (e) => {
    if (e) e.preventDefault();
    setLoading(true); setRoutes([]); setLogs([]); setError(null); setHasSearched(false);
    addLog('Scanning all confirmed channels...');
    try {
      const res = await fetch(`${API_BASE}/routes?source=${source}&destination=${dest}&date=${date}&max_connections=${maxConn}&min_layover_mins=${minLayover}&quota=${quota}`);
      if (!res.ok) throw new Error('Search failed');
      const data = await res.json();
      setRoutes(data);
      setHasSearched(true);
      addLog(`Scan complete. Found ${data.length} confirmed routes.`);
    } catch (err) {
      console.error(err);
      setError('Routing engine is temporarily unavailable.');
    } finally {
      setLoading(false);
    }
  };

  const sortedRoutes = useMemo(() => {
    return [...routes].sort((a, b) => {
      if (sortBy === 'duration') return a.total_duration_minutes - b.total_duration_minutes;
      if (sortBy === 'departure') return new Date(a.legs[0].departure_time) - new Date(b.legs[0].departure_time);
      if (sortBy === 'arrival') return new Date(a.legs[a.legs.length - 1].arrival_time) - new Date(b.legs[b.legs.length - 1].arrival_time);
      return 0;
    });
  }, [routes, sortBy]);

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 max-[600px]:px-3 max-[600px]:py-4">
      {/* Header */}
      <header className="flex items-center justify-between mb-10">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gradient-to-br from-indigo-500 to-indigo-600 rounded-xl flex items-center justify-center shadow-[0_8px_20px_rgba(99,102,241,0.3)]">
            <TrainIcon className="text-white" size={22} />
          </div>
          <h1 className="font-brand text-2xl font-black tracking-[-0.03em]">
            Sarvo<span className="text-indigo-500">Rail</span>
          </h1>
        </div>
        <div className="max-[600px]:hidden text-[0.7rem] text-gray-500 font-black uppercase tracking-[0.2em]">
          Indian Route Intelligence
        </div>
      </header>

      {/* Search card */}
      <div className="bg-white/[0.04] border border-white/[0.08] rounded-[1.5rem] p-8 max-[600px]:p-5 max-[600px]:rounded-2xl shadow-[0_25px_50px_-12px_rgba(0,0,0,0.5)] mb-6">
        <form onSubmit={handleSearch}>
          {/* 5-col desktop → 3-col tablet → 2-col mobile */}
          <div className="grid gap-3 items-end grid-cols-[1fr_36px_1fr_160px_auto] max-[900px]:grid-cols-[1fr_36px_1fr] max-[600px]:grid-cols-[1fr_44px] max-[600px]:grid-rows-4">

            {/* Origin */}
            <div className="max-[900px]:[grid-column:1] max-[900px]:[grid-row:1] max-[600px]:[grid-column:1] max-[600px]:[grid-row:1]">
              <label className="flex items-center gap-1 text-[0.75rem] font-bold text-gray-400 uppercase tracking-[0.1em] mb-2">
                <MapPin size={10} /> Origin
              </label>
              <StationInput value={source} onChange={setSource} placeholder="City or station code" onSelectName={updateStationName} stationNames={stationNames} />
            </div>

            {/* Swap — spans both station rows on mobile */}
            <div className="flex items-end pb-px max-[900px]:[grid-column:2] max-[900px]:[grid-row:1] max-[600px]:[grid-column:2] max-[600px]:[grid-row:1/3] max-[600px]:items-center max-[600px]:justify-center max-[600px]:pb-0">
              <button
                type="button"
                onClick={handleSwap}
                title="Swap origin and destination"
                className="w-9 h-10 bg-white/[0.04] border-[1.5px] border-white/[0.09] rounded-xl flex items-center justify-center cursor-pointer text-gray-500 hover:bg-indigo-500/[0.12] hover:text-indigo-500 hover:border-indigo-500/40 transition-all duration-200"
              >
                <ArrowUpDown size={15} />
              </button>
            </div>

            {/* Destination */}
            <div className="max-[900px]:[grid-column:3] max-[900px]:[grid-row:1] max-[600px]:[grid-column:1] max-[600px]:[grid-row:2]">
              <label className="flex items-center gap-1 text-[0.75rem] font-bold text-gray-400 uppercase tracking-[0.1em] mb-2">
                <MapPin size={10} /> Destination
              </label>
              <StationInput value={dest} onChange={setDest} placeholder="City or station code" onSelectName={updateStationName} stationNames={stationNames} />
            </div>

            {/* Date */}
            <div className="max-[900px]:[grid-column:1/3] max-[900px]:[grid-row:2] max-[600px]:[grid-column:1/-1] max-[600px]:[grid-row:3]">
              <label className="flex items-center gap-1 text-[0.75rem] font-bold text-gray-400 uppercase tracking-[0.1em] mb-2">
                <Calendar size={10} /> Date
              </label>
              <DatePicker value={date} onChange={setDate} />
            </div>

            {/* Filters + Search */}
            <div className="flex gap-2 max-[900px]:[grid-column:3] max-[900px]:[grid-row:2] max-[600px]:[grid-column:1/-1] max-[600px]:[grid-row:4]">
              <button
                type="button"
                onClick={() => setShowFilters(!showFilters)}
                title="Filters"
                className={`shrink-0 w-10 h-10 rounded-[14px] flex items-center justify-center cursor-pointer transition-all duration-200 border-[1.5px] ${
                  showFilters
                    ? 'bg-indigo-500/20 border-indigo-500/50 text-indigo-400'
                    : 'bg-white/[0.04] border-white/[0.09] text-gray-500'
                }`}
              >
                <SlidersHorizontal size={18} />
              </button>
              <button
                className="shrink-0 max-[600px]:flex-1 h-10 px-6 bg-gradient-to-br from-indigo-500 to-indigo-600 border-none rounded-[14px] text-white cursor-pointer shadow-[0_4px_15px_rgba(99,102,241,0.35)] flex items-center justify-center gap-2 font-bold tracking-[0.02em] transition-opacity disabled:opacity-70 hover:shadow-[0_8px_25px_rgba(99,102,241,0.45)] hover:-translate-y-px"
                disabled={loading}
              >
                {loading
                  ? <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  : <><span>Search Trains</span><ArrowRightCircle size={16} /></>
                }
              </button>
            </div>
          </div>

          {/* Filter panel */}
          <AnimatePresence>
            {showFilters && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                className="overflow-hidden"
              >
                <div className="grid grid-cols-[repeat(auto-fit,minmax(160px,1fr))] gap-6 mt-8 pt-8 border-t border-white/[0.05]">
                  <div>
                    <label className="text-[0.75rem] font-bold text-gray-400 uppercase tracking-[0.1em] mb-2 block">
                      Nearby Radius: <span className="text-indigo-400">{nearby}km</span>
                    </label>
                    <input type="range" min="0" max="100" step="10" value={nearby} onChange={e => setNearby(parseInt(e.target.value))} className="w-full accent-indigo-500" />
                  </div>
                  <div>
                    <label className="text-[0.75rem] font-bold text-gray-400 uppercase tracking-[0.1em] mb-2 block">
                      Max Connections: <span className="text-indigo-400">{maxConn}</span>
                    </label>
                    <div className="flex gap-1.5">
                      {[0, 1, 2].map(v => (
                        <button key={v} type="button" onClick={() => setMaxConn(v)}
                          className={`flex-1 py-2 text-[10px] font-black rounded-lg border transition-all duration-150 ${
                            maxConn === v ? 'bg-indigo-500 border-indigo-500 text-white' : 'bg-white/[0.03] border-white/[0.06] text-gray-500'
                          }`}>
                          {v === 0 ? 'DIRECT' : v}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div>
                    <label className="text-[0.75rem] font-bold text-gray-400 uppercase tracking-[0.1em] mb-2 block">
                      Min Layover: <span className="text-indigo-400">{minLayover < 60 ? `${minLayover}m` : `${minLayover / 60}h`}</span>
                    </label>
                    <div className="flex gap-1.5">
                      {[{ value: 30, label: '30m' }, { value: 60, label: '1h' }, { value: 90, label: '1.5h' }, { value: 120, label: '2h' }].map(opt => (
                        <button key={opt.value} type="button" onClick={() => setMinLayover(opt.value)}
                          className={`flex-1 py-2 text-[10px] font-black rounded-lg border transition-all duration-150 ${
                            minLayover === opt.value ? 'bg-indigo-500 border-indigo-500 text-white' : 'bg-white/[0.03] border-white/[0.06] text-gray-500'
                          }`}>
                          {opt.label}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div>
                    <label className="text-[0.75rem] font-bold text-gray-400 uppercase tracking-[0.1em] mb-2 block">
                      Quota: <span className="text-indigo-400">{quota === 'GN' ? 'General' : quota === 'TQ' ? 'Tatkal' : 'Premium Tatkal'}</span>
                    </label>
                    <div className="flex gap-1.5">
                      {['GN', 'TQ', 'PT'].map(v => (
                        <button key={v} type="button" onClick={() => setQuota(v)}
                          className={`flex-1 py-2 text-[10px] font-black rounded-lg border transition-all duration-150 ${
                            quota === v ? 'bg-indigo-500 border-indigo-500 text-white' : 'bg-white/[0.03] border-white/[0.06] text-gray-500'
                          }`}>
                          {v === 'GN' ? 'GEN' : v === 'TQ' ? 'TKL' : 'PTK'}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </form>

        {/* Console log */}
        {loading && (
          <div className="mt-6 p-4 bg-black/30 rounded-xl border border-white/[0.05] text-xs font-mono text-emerald-500">
            {logs.map((log, i) => <div key={i} className="mb-1">{log}</div>)}
          </div>
        )}
      </div>

      {/* App info — shown only before any search */}
      {!hasSearched && !loading && (
        <div className="mb-6 px-1 text-center">
          <p className="text-sm text-gray-500 leading-relaxed">
            SarvoRail finds train routes across India — including connections IRCTC won't show you.
            Enter your origin, destination and date, and we'll search direct as well as multi-train routes with live seat availability.
          </p>
          <div className="flex items-center justify-center gap-4 mt-4 text-[11px] text-gray-600 font-semibold">
            <span>🚆 Direct &amp; connecting routes</span>
            <span className="w-px h-3 bg-white/10" />
            <span>💺 Live seat availability</span>
            <span className="w-px h-3 bg-white/10" />
            <span>🎫 All quotas supported</span>
          </div>
        </div>
      )}

      {/* Sort tabs */}
      {routes.length > 0 && (
        <div className="flex gap-2 mb-6 overflow-x-auto pb-2 [scrollbar-width:none]">
          {[
            { id: 'duration', label: 'Fastest', icon: <Zap size={14} /> },
            { id: 'departure', label: 'Earliest', icon: <Sunrise size={14} /> },
            { id: 'arrival', label: 'Earliest Arrival', icon: <Sunset size={14} /> },
          ].map(opt => (
            <button
              key={opt.id}
              onClick={() => setSortBy(opt.id)}
              className={`flex items-center gap-1.5 px-4 py-2 rounded-xl text-[11px] font-black cursor-pointer whitespace-nowrap transition-all duration-200 border ${
                sortBy === opt.id
                  ? 'bg-indigo-500/10 border-indigo-500 text-white'
                  : 'bg-white/[0.02] border-white/[0.05] text-gray-500'
              }`}
            >
              {opt.icon}{opt.label}
            </button>
          ))}
        </div>
      )}

      {/* Results */}
      <div className="flex flex-col gap-5">
        {sortedRoutes.map((route, idx) => (
          <JourneyCard key={idx} route={route} isBest={idx === 0} stationNames={stationNames} />
        ))}

        {!loading && hasSearched && routes.length === 0 && !error && (
          <div className="text-center py-20 px-8 text-gray-600 border border-dashed border-white/[0.05] rounded-[2rem]">
            <div className="text-2xl mb-4">🚉</div>
            <div className="text-sm font-black text-gray-500 mb-2">No trains found for this route</div>
            <div className="text-xs text-gray-700 leading-7">
              This could mean no trains run between these stations on this date,<br />
              or IRCTC rate limiting prevented results from loading.<br />
              <span className="text-indigo-400 font-bold">Try: different date · more connections · nearby radius · check IRCTC directly</span>
            </div>
          </div>
        )}

        {error && (
          <div className="text-center py-10 text-red-400 text-sm font-semibold">{error}</div>
        )}
      </div>
    </div>
  );
}

function JourneyCard({ route, isBest, stationNames }) {
  const [open, setOpen] = useState(false);
  const startTime = new Date(route.legs[0].departure_time);
  const endTime = new Date(route.legs[route.legs.length - 1].arrival_time);
  const formatTime = (date) => date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
  const durationStr = `${Math.floor(route.total_duration_minutes / 60)}h ${route.total_duration_minutes % 60}m`;

  const mainTrainName = route.legs[0].train_name;
  const isDirect = route.connections === 0;
  const isConfirmed = route.is_fully_confirmed;
  const hasUnknownAvail = !isConfirmed && route.legs.some(l => l.availability.length === 0);
  const hasWl = !isConfirmed && route.legs.some(l =>
    l.availability.some(av => {
      const st = (av.status || '').toUpperCase();
      return (st.includes('WL') || st.includes('RAC')) && !st.includes('NOT');
    })
  );

  const cardBorder = isConfirmed ? 'border-emerald-500/15' : hasWl ? 'border-amber-500/15' : 'border-white/[0.05]';
  const cardBg = isConfirmed && isDirect ? 'bg-indigo-500/[0.05]' : 'bg-white/[0.02]';
  const leftAccent = isConfirmed ? 'border-l-emerald-500' : hasWl ? 'border-l-amber-500' : 'border-l-gray-600';

  return (
    <motion.div
      initial={{ y: 20, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      className={`p-6 max-[600px]:p-4 rounded-[20px] max-[600px]:rounded-2xl border border-l-4 transition-colors ${cardBorder} ${cardBg} ${leftAccent}`}
    >
      <div className="flex flex-col gap-5">

        {/* Title row */}
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-1.5 mb-1 flex-wrap">
              <span className="text-[0.65rem] text-indigo-500 font-black uppercase tracking-[0.1em]">
                {isDirect ? 'DIRECT JOURNEY' : `${route.connections} CONNECTION${route.connections > 1 ? 'S' : ''}`}
              </span>
              {isBest && isConfirmed && (
                <span className="text-[0.55rem] bg-emerald-500 text-white px-1.5 py-0.5 rounded font-black">BEST</span>
              )}
              {isConfirmed ? (
                <span className="text-[0.55rem] bg-emerald-500/15 text-emerald-500 px-2 py-0.5 rounded font-black border border-emerald-500/25">✓ SEATS AVAILABLE</span>
              ) : hasWl ? (
                <span className="text-[0.55rem] bg-amber-500/10 text-amber-400 px-2 py-0.5 rounded font-black border border-amber-500/25">⚠ WAITLISTED</span>
              ) : hasUnknownAvail ? (
                <span className="text-[0.55rem] bg-gray-500/10 text-gray-400 px-2 py-0.5 rounded font-black border border-gray-500/20">? CHECK IRCTC</span>
              ) : null}
            </div>
            <h2 className={`text-sm font-black tracking-tight ${isConfirmed ? 'text-white' : 'text-gray-400'}`}>
              {mainTrainName}
            </h2>
          </div>
          <div className="flex gap-2 shrink-0">
            {route.legs.map((l, i) => (
              <div key={i} className="text-[0.6rem] bg-white/[0.05] text-gray-400 px-2 py-[3px] rounded-md font-black border border-white/[0.08]">
                #{l.train_number}
              </div>
            ))}
          </div>
        </div>

        {/* Station path */}
        <div className="flex items-center gap-3 bg-black/25 px-4 py-2.5 rounded-xl w-fit flex-wrap">
          <span className="font-black text-sm text-white">{getStationLabel(route.legs[0].from_station, stationNames)}</span>
          {route.legs.map((leg, i) => (
            <React.Fragment key={i}>
              <ArrowRightCircle size={10} className="text-gray-600" />
              <span className={`font-black text-sm ${i === route.legs.length - 1 ? 'text-white' : 'text-indigo-400'}`}>
                {getStationLabel(leg.to_station, stationNames)}
              </span>
            </React.Fragment>
          ))}
        </div>

        {/* Time bar */}
        <div className="flex items-center gap-6 p-6 bg-white/[0.01] rounded-[1.25rem] border border-white/[0.03]">
          <div>
            <div className="text-base font-black text-white">{formatTime(startTime)}</div>
            <div className="text-[0.6rem] text-gray-500 font-black tracking-[0.05em]">DEPARTURE</div>
          </div>
          <div className="flex-1 flex flex-col items-center gap-1.5">
            <div className="w-full h-0.5 bg-white/[0.05] relative">
              <div className="absolute left-0 -top-[4px] w-2.5 h-2.5 bg-indigo-500 rounded-full shadow-[0_0_15px_rgba(99,102,241,0.6)]" />
              <div className="absolute right-0 -top-[4px] w-2.5 h-2.5 bg-indigo-500 rounded-full" />
            </div>
            <div className="text-[0.7rem] text-gray-600 font-black">{durationStr}</div>
          </div>
          <div className="text-right">
            <div className="text-base font-black text-white">{formatTime(endTime)}</div>
            <div className="text-[0.6rem] text-gray-500 font-black tracking-[0.05em]">ARRIVAL</div>
          </div>
        </div>

        {/* Per-leg availability */}
        <div className="flex gap-4 overflow-x-auto pb-2 [scrollbar-width:none]">
          {route.legs.map((leg, i) => (
            <div key={i} className="min-w-[220px] p-4 bg-black/25 rounded-2xl border border-white/[0.05]">
              <div className="text-[0.6rem] font-black text-gray-500 mb-3 tracking-[0.1em] flex flex-col gap-1">
                <span>{getStationLabel(leg.from_station, stationNames)}</span>
                {leg.booked_from_station && (
                  <div className="bg-emerald-500/10 text-emerald-500 px-2 py-1 rounded border border-emerald-500/20 w-fit">
                    PRO-TIP: BOOK FROM {getStationLabel(leg.booked_from_station, stationNames)}, BOARD AT {getStationLabel(leg.actual_boarding_station, stationNames)}
                  </div>
                )}
              </div>
              <div className="flex flex-col gap-1.5">
                {leg.availability.length === 0 && (
                  <div className="text-[10px] text-gray-600 font-bold py-1.5">Availability unknown — check IRCTC</div>
                )}
                {leg.availability.map((av, j) => {
                  const st = (av.status || '').toUpperCase();
                  const isAvbl = (st.includes('AVAILABLE') || st.includes('CURR_AVBL') || st.includes('AVBL')) && !st.includes('NOT');
                  const isWl   = !isAvbl && (st.includes('WAITLIST') || st.includes('WL') || st.includes('RLWL') || st.includes('PQWL') || st.includes('GNWL'));
                  const isRac  = !isAvbl && st.includes('RAC');
                  if (!isAvbl && !isWl && !isRac) return null;

                  const chipClass = isAvbl
                    ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-500'
                    : isWl
                    ? 'bg-amber-500/[0.08] border-amber-500/20 text-amber-400'
                    : 'bg-indigo-500/[0.08] border-indigo-500/20 text-indigo-400';

                  const label = isAvbl
                    ? (av.available_count != null ? `${av.available_count} seats` : 'AVBL')
                    : isWl ? `WL ${av.waitlist_number ?? ''}` : `RAC ${av.waitlist_number ?? ''}`;

                  return (
                    <div key={j} className={`flex items-center justify-between px-2.5 py-[7px] rounded-lg border ${chipClass}`}>
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-black">{av.class_code}</span>
                        <span className="text-[11px] font-black text-white">{label}</span>
                      </div>
                      {av.fare && <span className="text-[11px] font-black text-indigo-400">₹{av.fare}</span>}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>

        {/* Detailed timeline toggle */}
        {route.connections > 0 && (
          <div
            onClick={() => setOpen(!open)}
            className="text-center cursor-pointer text-[0.65rem] font-black text-gray-600 uppercase tracking-[0.15em] mt-1 hover:text-gray-400 transition-colors"
          >
            {open ? 'Hide Detailed Timeline' : 'Show Detailed Timeline'}
          </div>
        )}

        <AnimatePresence>
          {open && (
            <motion.div initial={{ height: 0 }} animate={{ height: 'auto' }} exit={{ height: 0 }} className="overflow-hidden">
              <div className="py-4 flex flex-col gap-3">
                {route.legs.map((leg, i) => (
                  <div key={i} className="p-4 bg-white/[0.02] rounded-xl border border-white/[0.03]">
                    <div className="flex justify-between mb-2 gap-4 flex-wrap">
                      <span className="text-white font-black text-sm">
                        {leg.train_name} <span className="text-indigo-500/80">#{leg.train_number}</span>
                      </span>
                      <div className="flex flex-col items-end">
                        <span className="text-emerald-500 font-black text-sm">{formatTime(new Date(leg.departure_time))} – {formatTime(new Date(leg.arrival_time))}</span>
                        <span className="text-gray-600 text-[0.6rem] font-black">{leg.date} · GENERAL QUOTA</span>
                      </div>
                    </div>
                    <div className="text-gray-500 text-[0.7rem] font-bold flex items-center gap-2 flex-wrap">
                      <span className="text-white">{getStationLabel(leg.from_station, stationNames)}</span>
                      <ArrowRightCircle size={10} />
                      <span className="text-white">{getStationLabel(leg.to_station, stationNames)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

      </div>
    </motion.div>
  );
}

export default App;
