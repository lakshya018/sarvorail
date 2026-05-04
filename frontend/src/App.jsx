import React, { useState, useMemo, useEffect, useRef } from 'react';
import axios from 'axios';
import {
  Clock,
  ChevronDown,
  Navigation,
  Activity,
  ArrowRightCircle,
  Train,
  CheckCircle,
  AlertCircle,
  Hash,
  Ticket,
  SlidersHorizontal,
  MapPin,
  Calendar,
  Layers,
  Wind,
  ArrowUpDown,
  Zap,
  Sunrise,
  Sunset,
  Banknote,
  Train as TrainIcon,
  Search
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000/api/v1';

// Helper to get full station label
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

  // Sync display label when value is changed externally (e.g. swap button)
  useEffect(() => {
    const name = stationNames[value];
    setInputDisplay(name ? `${name} (${value})` : (value || ''));
  }, [value]); // eslint-disable-line react-hooks/exhaustive-deps

  const fetchSuggestions = (q) => {
    clearTimeout(debounceRef.current);
    if (!q || q.length < 2) {
      setSuggestions([]);
      setShowSuggestions(false);
      return;
    }
    debounceRef.current = setTimeout(async () => {
      setLoading(true);
      try {
        const res = await fetch(`${API_BASE}/stations/search?query=${encodeURIComponent(q)}`);
        const data = await res.json();
        setSuggestions(data);
        setActiveIndex(-1);
        setShowSuggestions(data.length > 0);
      } catch {
        setSuggestions([]);
      } finally {
        setLoading(false);
      }
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
      setActiveIndex(next);
      scrollActiveIntoView(next);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      const next = Math.max(activeIndex - 1, 0);
      setActiveIndex(next);
      scrollActiveIntoView(next);
    } else if (e.key === 'Enter' && activeIndex >= 0) {
      e.preventDefault();
      handleSelect(suggestions[activeIndex]);
    } else if (e.key === 'Escape') {
      setShowSuggestions(false);
      setActiveIndex(-1);
    }
  };

  const borderColor = isFocused ? 'rgba(99, 102, 241, 0.55)' : 'rgba(255,255,255,0.09)';
  const boxShadow = isFocused ? '0 0 0 4px rgba(99, 102, 241, 0.1)' : 'none';

  return (
    <div style={{ position: 'relative', width: '100%' }}>
      {/* Input wrapper — acts as the styled container */}
      <div style={{
        position: 'relative',
        background: 'rgba(255,255,255,0.04)',
        border: `1.5px solid ${borderColor}`,
        borderRadius: '14px',
        boxShadow,
        transition: 'border-color 0.2s, box-shadow 0.2s',
      }}>
        <MapPin
          size={15}
          style={{
            position: 'absolute', left: '13px', top: '50%', transform: 'translateY(-50%)',
            color: isFocused ? '#6366f1' : '#4b5563',
            transition: 'color 0.2s', pointerEvents: 'none',
          }}
        />
        <input
          ref={inputRef}
          type="text"
          value={inputDisplay}
          onChange={(e) => {
            setInputDisplay(e.target.value);
            fetchSuggestions(e.target.value);
          }}
          onFocus={(e) => {
            setIsFocused(true);
            if (suggestions.length > 0) setShowSuggestions(true);
            // Select all so user can immediately type a new search
            setTimeout(() => e.target.select(), 0);
          }}
          onBlur={() => {
            setIsFocused(false);
            // Delay so onMouseDown on a suggestion fires first
            setTimeout(() => setShowSuggestions(false), 150);
          }}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          style={{
            width: '100%', height: '52px',
            background: 'transparent', border: 'none', outline: 'none',
            paddingLeft: '2.25rem',
            paddingRight: inputDisplay ? '2.25rem' : '0.75rem',
            color: '#f1f5f9', fontSize: '0.875rem', fontWeight: '600',
            letterSpacing: '0.01em',
          }}
        />

        {/* Clear (×) button */}
        {inputDisplay && (
          <button
            type="button"
            onMouseDown={(e) => {
              e.preventDefault(); // prevent blur before clear
              setInputDisplay('');
              onChange('');
              setSuggestions([]);
              setShowSuggestions(false);
              inputRef.current?.focus();
            }}
            style={{
              position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)',
              background: 'rgba(255,255,255,0.08)', border: 'none', borderRadius: '50%',
              width: '20px', height: '20px', display: 'flex', alignItems: 'center',
              justifyContent: 'center', cursor: 'pointer', color: '#6b7280',
              fontSize: '14px', fontWeight: '400', padding: 0, lineHeight: 1,
            }}
          >
            ×
          </button>
        )}

        {/* Loading spinner */}
        {loading && (
          <div
            className="animate-spin"
            style={{
              position: 'absolute',
              right: inputDisplay ? '38px' : '13px',
              top: '50%', transform: 'translateY(-50%)',
              width: '13px', height: '13px',
              border: '2px solid rgba(99,102,241,0.2)',
              borderTopColor: '#6366f1', borderRadius: '50%',
            }}
          />
        )}
      </div>

      {/* Dropdown */}
      <AnimatePresence>
        {showSuggestions && suggestions.length > 0 && (
          <motion.div
            ref={listRef}
            initial={{ opacity: 0, y: -8, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.97 }}
            transition={{ duration: 0.13, ease: 'easeOut' }}
            style={{
              position: 'absolute', zIndex: 200, width: '100%',
              top: 'calc(100% + 6px)',
              background: 'rgba(10, 12, 24, 0.98)',
              backdropFilter: 'blur(24px)',
              border: '1px solid rgba(99, 102, 241, 0.2)',
              borderRadius: '16px',
              boxShadow: '0 24px 60px rgba(0,0,0,0.65), inset 0 0 0 1px rgba(255,255,255,0.03)',
              overflow: 'hidden',
              maxHeight: '300px', overflowY: 'auto',
              scrollbarWidth: 'thin', scrollbarColor: 'rgba(99,102,241,0.25) transparent',
            }}
          >
            {/* Sticky header */}
            <div style={{
              position: 'sticky', top: 0, zIndex: 1,
              padding: '9px 14px 8px',
              background: 'rgba(10, 12, 24, 0.98)',
              borderBottom: '1px solid rgba(255,255,255,0.05)',
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            }}>
              <span style={{ fontSize: '9px', color: '#4b5563', fontWeight: '800', letterSpacing: '0.12em', textTransform: 'uppercase' }}>
                {suggestions.length} stations
              </span>
              <span style={{ fontSize: '9px', color: '#1f2937', fontWeight: '700', letterSpacing: '0.04em' }}>
                ↑↓ · ↵ select · esc
              </span>
            </div>

            {/* Suggestion rows */}
            {suggestions.map((s, i) => {
              const isActive = i === activeIndex;
              return (
                <div
                  key={s.station_code}
                  data-idx={i}
                  onMouseDown={() => handleSelect(s)}
                  onMouseEnter={() => setActiveIndex(i)}
                  style={{
                    display: 'flex', alignItems: 'center', gap: '11px',
                    padding: '10px 14px',
                    cursor: 'pointer',
                    borderLeft: `3px solid ${isActive ? '#6366f1' : 'transparent'}`,
                    borderBottom: i < suggestions.length - 1 ? '1px solid rgba(255,255,255,0.03)' : 'none',
                    background: isActive ? 'rgba(99,102,241,0.1)' : 'transparent',
                    transition: 'background 0.08s',
                  }}
                >
                  {/* Station code badge */}
                  <div style={{
                    flexShrink: 0,
                    minWidth: '42px',
                    padding: '3px 6px',
                    background: isActive ? 'rgba(99,102,241,0.22)' : 'rgba(255,255,255,0.05)',
                    border: `1px solid ${isActive ? 'rgba(99,102,241,0.4)' : 'rgba(255,255,255,0.07)'}`,
                    borderRadius: '6px',
                    textAlign: 'center',
                    fontSize: '10px', fontWeight: '900',
                    color: isActive ? '#a5b4fc' : '#6b7280',
                    letterSpacing: '0.04em',
                  }}>
                    {s.station_code}
                  </div>

                  {/* Name + state */}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{
                      fontSize: '13px', fontWeight: '600',
                      color: isActive ? '#f1f5f9' : '#cbd5e1',
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    }}>
                      {s.station_name}
                    </div>
                    <div style={{
                      fontSize: '10px', color: '#374151', fontWeight: '700',
                      marginTop: '1px', letterSpacing: '0.04em', textTransform: 'uppercase',
                    }}>
                      {s.state}
                    </div>
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

function App() {
  const [source, setSource] = useState('KK');
  const [dest, setDest] = useState('SNGN');
  const [date, setDate] = useState('2026-05-04');
  const [nearby, setNearby] = useState(0);
  const [maxConn, setMaxConn] = useState(2);
  const [minLayover, setMinLayover] = useState(30);
  const [maxLayover, setMaxLayover] = useState(240);
  const [quota, setQuota] = useState('GN');
  const [showFilters, setShowFilters] = useState(false);
  const [sortBy, setSortBy] = useState('duration');

  const [loading, setLoading] = useState(false);
  const [routes, setRoutes] = useState([]);
  const [logs, setLogs] = useState([]);
  const [error, setError] = useState(null);
  const [stationNames, setStationNames] = useState({});

  const updateStationName = (code, name) => {
    setStationNames(prev => ({ ...prev, [code]: name }));
  };

  const handleSwap = () => {
    setSource(dest);
    setDest(source);
  };

  const addLog = (msg) => {
    setLogs(prev => [`> ${msg}`, ...prev].slice(0, 5));
  };

  const handleSearch = async (e) => {
    if (e) e.preventDefault();
    setLoading(true);
    setRoutes([]);
    setLogs([]);
    setError(null);

    addLog(`Scanning all confirmed channels...`);

    try {
      const res = await fetch(`${API_BASE}/routes?source=${source}&destination=${dest}&date=${date}&max_connections=${maxConn}&min_layover_mins=${minLayover}&quota=${quota}`);
      if (!res.ok) throw new Error("Search failed");
      const data = await res.json();
      setRoutes(data);
      addLog(`Scan complete. Found ${data.length} confirmed routes.`);
    } catch (err) {
      console.error(err);
      setError("Routing engine is temporarily unavailable.");
    } finally {
      setLoading(false);
    }
  };

  const sortedRoutes = useMemo(() => {
    const list = [...routes];
    return list.sort((a, b) => {
      if (sortBy === 'duration') return a.total_duration_minutes - b.total_duration_minutes;
      if (sortBy === 'departure') return new Date(a.legs[0].departure_time) - new Date(b.legs[0].departure_time);
      if (sortBy === 'arrival') return new Date(a.legs[a.legs.length - 1].arrival_time) - new Date(b.legs[b.legs.length - 1].arrival_time);
      return 0;
    });
  }, [routes, sortBy]);

  return (
    <div className="app-container">
      <header style={{ marginBottom: '2.5rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div style={{ width: '40px', height: '40px', background: 'linear-gradient(135deg, #6366f1, #4f46e5)', borderRadius: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 8px 20px rgba(99, 102, 241, 0.3)' }}>
            <TrainIcon style={{ color: 'white' }} size={22} />
          </div>
          <h1 className="brand-font" style={{ fontSize: '1.85rem', fontWeight: '900', letterSpacing: '-0.03em' }}>
            Sarvo<span style={{ color: '#6366f1' }}>Rail</span>
          </h1>
        </div>
        <div style={{ fontSize: '0.7rem', color: '#6b7280', fontWeight: '900', textTransform: 'uppercase', letterSpacing: '0.2em' }}>
          Indian Route Intelligence
        </div>
      </header>

      <div className="search-card" style={{ marginBottom: '1.5rem' }}>
        <form onSubmit={handleSearch}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 36px 1fr 160px auto', gap: '0.75rem', alignItems: 'end' }}>

            {/* Origin */}
            <div>
              <label className="input-label"><MapPin size={10} style={{ marginRight: '4px' }} /> Origin</label>
              <StationInput
                value={source}
                onChange={setSource}
                placeholder="City or station code"
                onSelectName={updateStationName}
                stationNames={stationNames}
              />
            </div>

            {/* Swap button */}
            <div style={{ display: 'flex', alignItems: 'flex-end', paddingBottom: '1px' }}>
              <button
                type="button"
                onClick={handleSwap}
                title="Swap origin and destination"
                style={{
                  width: '36px', height: '52px',
                  background: 'rgba(255,255,255,0.04)',
                  border: '1.5px solid rgba(255,255,255,0.09)',
                  borderRadius: '12px',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  cursor: 'pointer', color: '#6b7280',
                  transition: 'background 0.2s, color 0.2s, border-color 0.2s',
                }}
                onMouseEnter={e => {
                  e.currentTarget.style.background = 'rgba(99,102,241,0.12)';
                  e.currentTarget.style.color = '#6366f1';
                  e.currentTarget.style.borderColor = 'rgba(99,102,241,0.35)';
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.background = 'rgba(255,255,255,0.04)';
                  e.currentTarget.style.color = '#6b7280';
                  e.currentTarget.style.borderColor = 'rgba(255,255,255,0.09)';
                }}
              >
                <ArrowUpDown size={15} />
              </button>
            </div>

            {/* Destination */}
            <div>
              <label className="input-label"><MapPin size={10} style={{ marginRight: '4px' }} /> Destination</label>
              <StationInput
                value={dest}
                onChange={setDest}
                placeholder="City or station code"
                onSelectName={updateStationName}
                stationNames={stationNames}
              />
            </div>

            {/* Date */}
            <div>
              <label className="input-label"><Calendar size={10} style={{ marginRight: '4px' }} /> Date</label>
              <div style={{ position: 'relative' }}>
                <Calendar 
                  size={16} 
                  style={{ 
                    position: 'absolute', 
                    left: '14px', 
                    top: '50%', 
                    transform: 'translateY(-50%)', 
                    color: '#6366f1',
                    pointerEvents: 'none'
                  }} 
                />
                <input
                  type="date"
                  className="premium-date-input"
                  value={date}
                  onChange={e => setDate(e.target.value)}
                  style={{
                    width: '100%', height: '52px',
                    background: 'rgba(255,255,255,0.04)',
                    border: '1.5px solid rgba(255,255,255,0.09)',
                    borderRadius: '14px',
                    padding: '0 1rem 0 2.5rem', color: '#fff',
                    fontSize: '0.875rem', fontWeight: '600',
                    outline: 'none',
                    transition: 'border-color 0.2s, box-shadow 0.2s',
                    cursor: 'pointer'
                  }}
                  onFocus={e => {
                    e.target.style.borderColor = 'rgba(99, 102, 241, 0.55)';
                    e.target.style.boxShadow = '0 0 0 4px rgba(99, 102, 241, 0.1)';
                  }}
                  onBlur={e => {
                    e.target.style.borderColor = 'rgba(255,255,255,0.09)';
                    e.target.style.boxShadow = 'none';
                  }}
                />
              </div>
            </div>

            {/* Filters + Search */}
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button
                type="button"
                onClick={() => setShowFilters(!showFilters)}
                title="Filters"
                style={{
                  flexShrink: 0,
                  width: '52px', height: '52px',
                  borderRadius: '14px',
                  background: showFilters ? 'rgba(99,102,241,0.2)' : 'rgba(255,255,255,0.04)',
                  border: showFilters ? '1.5px solid rgba(99,102,241,0.5)' : '1.5px solid rgba(255,255,255,0.09)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  cursor: 'pointer',
                  color: showFilters ? '#818cf8' : '#6b7280',
                  transition: 'all 0.2s',
                }}
              >
                <SlidersHorizontal size={18} />
              </button>
              <button
                className="search-btn"
                disabled={loading}
                style={{
                  flexShrink: 0,
                  height: '52px',
                  padding: '0 1.5rem',
                  background: 'linear-gradient(135deg, #6366f1, #4f46e5)',
                  border: 'none', borderRadius: '14px',
                  color: '#fff', cursor: 'pointer',
                  boxShadow: '0 4px 15px rgba(99,102,241,0.35)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px',
                  transition: 'opacity 0.2s',
                  opacity: loading ? 0.7 : 1,
                  fontWeight: '700',
                  letterSpacing: '0.02em',
                }}
              >
                {loading
                  ? <div className="animate-spin" style={{ width: '16px', height: '16px', border: '2px solid rgba(255,255,255,0.3)', borderTopColor: '#fff', borderRadius: '50%' }} />
                  : (
                    <>
                      <span>Search Trains</span>
                      <ArrowRightCircle size={16} />
                    </>
                  )
                }
              </button>
            </div>
          </div>

          <AnimatePresence>
            {showFilters && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                style={{ overflow: 'hidden' }}
              >
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '1.5rem', marginTop: '2rem', paddingTop: '2rem', borderTop: '1px solid rgba(255,255,255,0.05)' }}>
                  <div>
                    <label className="input-label">Nearby Radius: <span style={{ color: '#6366f1' }}>{nearby}km</span></label>
                    <input type="range" min="0" max="100" step="10" value={nearby} onChange={e => setNearby(parseInt(e.target.value))} style={{ width: '100%', accentColor: '#6366f1' }} />
                  </div>
                  <div>
                    <label className="input-label">Max Connections: <span style={{ color: '#6366f1' }}>{maxConn}</span></label>
                    <div style={{ display: 'flex', gap: '5px' }}>
                      {[0, 1, 2].map(v => (
                        <button
                          key={v}
                          type="button"
                          onClick={() => setMaxConn(v)}
                          style={{
                            flex: 1, padding: '8px 4px',
                            fontSize: '10px', fontWeight: '800', borderRadius: '8px',
                            background: maxConn === v ? '#6366f1' : 'rgba(255,255,255,0.03)',
                            border: maxConn === v ? '1px solid #6366f1' : '1px solid rgba(255,255,255,0.06)',
                            color: maxConn === v ? '#fff' : '#6b7280',
                            cursor: 'pointer', transition: 'all 0.15s',
                          }}
                        >
                          {v === 0 ? 'DIRECT' : v}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div>
                    <label className="input-label">
                      Min Layover: <span style={{ color: '#6366f1' }}>
                        {minLayover < 60 ? `${minLayover}m` : `${minLayover / 60}h`}
                      </span>
                    </label>
                    <div style={{ display: 'flex', gap: '5px' }}>
                      {[
                        { value: 30,  label: '30m' },
                        { value: 60,  label: '1h'  },
                        { value: 90,  label: '1.5h' },
                        { value: 120, label: '2h'  },
                      ].map(opt => (
                        <button
                          key={opt.value}
                          type="button"
                          onClick={() => setMinLayover(opt.value)}
                          style={{
                            flex: 1, padding: '8px 4px',
                            fontSize: '10px', fontWeight: '800', borderRadius: '8px',
                            background: minLayover === opt.value ? '#6366f1' : 'rgba(255,255,255,0.03)',
                            border: minLayover === opt.value ? '1px solid #6366f1' : '1px solid rgba(255,255,255,0.06)',
                            color: minLayover === opt.value ? '#fff' : '#6b7280',
                            cursor: 'pointer', transition: 'all 0.15s',
                          }}
                        >
                          {opt.label}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div>
                    <label className="input-label">Quota: <span style={{ color: '#6366f1' }}>{quota === 'GN' ? 'General' : quota === 'TQ' ? 'Tatkal' : 'Premium Tatkal'}</span></label>
                    <div style={{ display: 'flex', gap: '5px' }}>
                      {['GN', 'TQ', 'PT'].map(v => (
                        <button
                          key={v}
                          type="button"
                          onClick={() => setQuota(v)}
                          style={{
                            flex: 1, padding: '8px 4px',
                            fontSize: '10px', fontWeight: '800', borderRadius: '8px',
                            background: quota === v ? '#6366f1' : 'rgba(255,255,255,0.03)',
                            border: quota === v ? '1px solid #6366f1' : '1px solid rgba(255,255,255,0.06)',
                            color: quota === v ? '#fff' : '#6b7280',
                            cursor: 'pointer', transition: 'all 0.15s',
                          }}
                        >
                          {v === 'GN' ? 'GENERAL' : v === 'TQ' ? 'TATKAL' : 'PREM. TATKAL'}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </form>

        {loading && (
          <div className="console-container" style={{ marginTop: '1.5rem', padding: '1rem', background: 'rgba(0,0,0,0.3)', borderRadius: '10px', border: '1px solid rgba(255,255,255,0.05)', fontSize: '0.7rem', fontFamily: 'monospace', color: '#10b981' }}>
            {logs.map((log, i) => <div key={i} style={{ marginBottom: '4px' }}>{log}</div>)}
          </div>
        )}
      </div>

      {routes.length > 0 && (
        <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem', overflowX: 'auto', paddingBottom: '0.5rem', scrollbarWidth: 'none' }}>
          {[
            { id: 'duration', label: 'Fastest', icon: <Zap size={14} /> },
            { id: 'departure', label: 'Earliest', icon: <Sunrise size={14} /> },
            { id: 'arrival', label: 'Earliest Arrival', icon: <Sunset size={14} /> }
          ].map(opt => (
            <button
              key={opt.id}
              onClick={() => setSortBy(opt.id)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '8px 16px',
                borderRadius: '10px',
                background: sortBy === opt.id ? 'rgba(99, 102, 241, 0.1)' : 'rgba(255,255,255,0.02)',
                border: sortBy === opt.id ? '1px solid #6366f1' : '1px solid rgba(255,255,255,0.05)',
                color: sortBy === opt.id ? '#fff' : '#6b7280',
                fontSize: '11px',
                fontWeight: '800',
                cursor: 'pointer',
                whiteSpace: 'nowrap',
                transition: 'all 0.2s ease'
              }}
            >
              {opt.icon}
              {opt.label}
            </button>
          ))}
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
        {sortedRoutes.map((route, idx) => (
          <JourneyCard key={idx} route={route} isBest={idx === 0} stationNames={stationNames} />
        ))}

        {!loading && routes.length === 0 && !error && (
          <div style={{ textAlign: 'center', padding: '5rem 2rem', color: '#4b5563', border: '1px dashed rgba(255,255,255,0.05)', borderRadius: '2rem' }}>
            <div style={{ fontSize: '2rem', marginBottom: '1rem' }}>🚉</div>
            <div style={{ fontSize: '0.95rem', fontWeight: '800', color: '#6b7280', marginBottom: '0.5rem' }}>No trains found for this route</div>
            <div style={{ fontSize: '0.75rem', color: '#374151', lineHeight: 1.7 }}>
              This could mean no trains run between these stations on this date,<br />
              or IRCTC rate limiting prevented results from loading.<br />
              <span style={{ color: '#6366f1', fontWeight: '700' }}>Try: different date · more connections · nearby radius · check IRCTC directly</span>
            </div>
          </div>
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

  const accentColor = isConfirmed ? '#10b981' : hasWl ? '#f59e0b' : '#6b7280';

  return (
    <motion.div
      initial={{ y: 20, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      className="route-card"
      style={{
        padding: '1.5rem',
        borderRadius: '20px',
        border: `1px solid ${isConfirmed ? 'rgba(16,185,129,0.15)' : hasWl ? 'rgba(245,158,11,0.15)' : 'rgba(255,255,255,0.05)'}`,
        background: isConfirmed
          ? (isDirect ? 'rgba(99,102,241,0.05)' : 'rgba(255,255,255,0.02)')
          : 'rgba(255,255,255,0.015)',
        borderLeft: `4px solid ${isBest && isConfirmed ? '#10b981' : accentColor}`,
      }}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px', flexWrap: 'wrap' }}>
              <div style={{ fontSize: '0.65rem', color: '#6366f1', fontWeight: '900', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
                {isDirect ? 'DIRECT JOURNEY' : `${route.connections} CONNECTION${route.connections > 1 ? 'S' : ''}`}
              </div>
              {isBest && isConfirmed && (
                <span style={{ fontSize: '0.55rem', background: '#10b981', color: '#fff', padding: '2px 6px', borderRadius: '4px', fontWeight: '900' }}>BEST</span>
              )}
              {isConfirmed ? (
                <span style={{ fontSize: '0.55rem', background: 'rgba(16,185,129,0.15)', color: '#10b981', padding: '2px 8px', borderRadius: '4px', fontWeight: '900', border: '1px solid rgba(16,185,129,0.25)' }}>✓ SEATS AVAILABLE</span>
              ) : hasWl ? (
                <span style={{ fontSize: '0.55rem', background: 'rgba(245,158,11,0.12)', color: '#f59e0b', padding: '2px 8px', borderRadius: '4px', fontWeight: '900', border: '1px solid rgba(245,158,11,0.25)' }}>⚠ WAITLISTED</span>
              ) : hasUnknownAvail ? (
                <span style={{ fontSize: '0.55rem', background: 'rgba(107,114,128,0.12)', color: '#9ca3af', padding: '2px 8px', borderRadius: '4px', fontWeight: '900', border: '1px solid rgba(107,114,128,0.2)' }}>? CHECK IRCTC</span>
              ) : null}
            </div>
            <h2 style={{ fontSize: '1.2rem', fontWeight: '900', color: isConfirmed ? '#fff' : '#9ca3af', margin: 0, letterSpacing: '-0.01em' }}>
              {mainTrainName}
            </h2>
          </div>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            {route.legs.map((l, i) => (
              <div key={i} style={{ fontSize: '0.6rem', background: 'rgba(255,255,255,0.05)', color: '#9ca3af', padding: '3px 8px', borderRadius: '6px', fontWeight: '800', border: '1px solid rgba(255,255,255,0.08)' }}>
                #{l.train_number}
              </div>
            ))}
          </div>
        </div>

        {/* Route Visualization */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', background: 'rgba(0,0,0,0.25)', padding: '0.6rem 1rem', borderRadius: '10px', width: 'fit-content' }}>
          <span style={{ fontWeight: '900', fontSize: '0.8rem', color: '#fff' }}>{getStationLabel(route.legs[0].from_station, stationNames)}</span>
          {route.legs.map((leg, i) => (
            <React.Fragment key={i}>
              <ArrowRightCircle size={10} style={{ color: '#4b5563' }} />
              <span style={{ fontWeight: '900', fontSize: '0.8rem', color: i === route.legs.length - 1 ? '#fff' : '#6366f1' }}>
                {getStationLabel(leg.to_station, stationNames)}
              </span>
            </React.Fragment>
          ))}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem', padding: '1.5rem', background: 'rgba(255,255,255,0.01)', borderRadius: '1.25rem', border: '1px solid rgba(255,255,255,0.03)' }}>
          <div style={{ textAlign: 'left' }}>
            <div style={{ fontSize: '1.4rem', fontWeight: '900', color: '#fff' }}>{formatTime(startTime)}</div>
            <div style={{ fontSize: '0.6rem', color: '#6b7280', fontWeight: '800', letterSpacing: '0.05em' }}>DEPARTURE</div>
          </div>

          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.4rem' }}>
            <div style={{ width: '100%', height: '2px', background: 'rgba(255,255,255,0.05)', position: 'relative' }}>
              <div style={{ position: 'absolute', left: 0, top: '-4px', width: '10px', height: '10px', background: '#6366f1', borderRadius: '50%', boxShadow: '0 0 15px rgba(99, 102, 241, 0.6)' }}></div>
              <div style={{ position: 'absolute', right: 0, top: '-4px', width: '10px', height: '10px', background: '#6366f1', borderRadius: '50%' }}></div>
            </div>
            <div style={{ fontSize: '0.7rem', color: '#4b5563', fontWeight: '900' }}>{durationStr}</div>
          </div>

          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: '1.4rem', fontWeight: '900', color: '#fff' }}>{formatTime(endTime)}</div>
            <div style={{ fontSize: '0.6rem', color: '#6b7280', fontWeight: '800', letterSpacing: '0.05em' }}>ARRIVAL</div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '1rem', overflowX: 'auto', paddingBottom: '0.5rem', scrollbarWidth: 'none' }}>
          {route.legs.map((leg, i) => (
            <div key={i} style={{ minWidth: '220px', padding: '1rem', background: 'rgba(0,0,0,0.25)', borderRadius: '1rem', border: '1px solid rgba(255,255,255,0.05)' }}>
              <div style={{ fontSize: '0.6rem', fontWeight: '900', color: '#6b7280', marginBottom: '0.75rem', letterSpacing: '0.1em', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <span>{getStationLabel(leg.from_station, stationNames)}</span>
                {leg.booked_from_station && (
                  <div style={{ background: 'rgba(16, 185, 129, 0.1)', color: '#10b981', padding: '4px 8px', borderRadius: '4px', border: '1px solid rgba(16, 185, 129, 0.2)', width: 'fit-content' }}>
                    PRO-TIP: BOOK FROM {getStationLabel(leg.booked_from_station, stationNames)}, BOARD AT {getStationLabel(leg.actual_boarding_station, stationNames)}
                  </div>
                )}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {leg.availability.length === 0 && (
                  <div style={{ fontSize: '10px', color: '#4b5563', fontWeight: '700', padding: '6px 0' }}>
                    Availability unknown — check IRCTC
                  </div>
                )}
                {leg.availability.map((av, j) => {
                  const st = (av.status || '').toUpperCase();
                  const isAvbl = (st.includes('AVAILABLE') || st.includes('CURR_AVBL') || st.includes('AVBL')) && !st.includes('NOT');
                  const isWl   = !isAvbl && (st.includes('WAITLIST') || st.includes('WL') || st.includes('RLWL') || st.includes('PQWL') || st.includes('GNWL'));
                  const isRac  = !isAvbl && st.includes('RAC');

                  // Hide only genuine NOT_AVAILABLE (class doesn't exist / train doesn't run)
                  if (!isAvbl && !isWl && !isRac) return null;

                  const bg     = isAvbl ? 'rgba(16,185,129,0.1)'  : isWl ? 'rgba(245,158,11,0.08)' : 'rgba(99,102,241,0.08)';
                  const border = isAvbl ? 'rgba(16,185,129,0.2)'  : isWl ? 'rgba(245,158,11,0.2)'  : 'rgba(99,102,241,0.2)';
                  const color  = isAvbl ? '#10b981'               : isWl ? '#f59e0b'               : '#818cf8';

                  const label = isAvbl
                    ? (av.available_count != null ? `${av.available_count} seats` : 'AVBL')
                    : isWl
                    ? `WL ${av.waitlist_number ?? ''}`
                    : `RAC ${av.waitlist_number ?? ''}`;

                  return (
                    <div key={j} style={{
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                      background: bg, padding: '7px 10px', borderRadius: '8px',
                      border: `1px solid ${border}`,
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontSize: '10px', fontWeight: '900', color }}>{av.class_code}</span>
                        <span style={{ fontSize: '11px', fontWeight: '800', color: '#fff' }}>{label}</span>
                      </div>
                      {av.fare && (
                        <span style={{ fontSize: '11px', fontWeight: '900', color: '#6366f1' }}>₹{av.fare}</span>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>

        {route.connections > 0 && (
          <div
            onClick={() => setOpen(!open)}
            style={{ textAlign: 'center', cursor: 'pointer', fontSize: '0.65rem', fontWeight: '900', color: '#4b5563', textTransform: 'uppercase', letterSpacing: '0.15em', marginTop: '0.5rem' }}
          >
            {open ? 'Hide Detailed Timeline' : 'Show Detailed Timeline'}
          </div>
        )}

        <AnimatePresence>
          {open && (
            <motion.div initial={{ height: 0 }} animate={{ height: 'auto' }} exit={{ height: 0 }} style={{ overflow: 'hidden' }}>
              <div style={{ padding: '1rem 0', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {route.legs.map((leg, i) => (
                  <div key={i} style={{ padding: '1rem', background: 'rgba(255,255,255,0.02)', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.03)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                      <span style={{ color: '#fff', fontWeight: '800', fontSize: '0.85rem' }}>
                        {leg.train_name} <span style={{ color: '#6366f1', opacity: 0.8 }}>#{leg.train_number}</span>
                      </span>
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end' }}>
                        <span style={{ color: '#10b981', fontWeight: '900', fontSize: '0.85rem' }}>{formatTime(new Date(leg.departure_time))} - {formatTime(new Date(leg.arrival_time))}</span>
                        <span style={{ color: '#4b5563', fontSize: '0.6rem', fontWeight: '900' }}>{leg.date} • GENERAL QUOTA</span>
                      </div>
                    </div>
                    <div style={{ color: '#6b7280', fontSize: '0.7rem', fontWeight: '700', display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{ color: '#fff' }}>{getStationLabel(leg.from_station, stationNames)}</span>
                      <ArrowRightCircle size={10} />
                      <span style={{ color: '#fff' }}>{getStationLabel(leg.to_station, stationNames)}</span>
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
