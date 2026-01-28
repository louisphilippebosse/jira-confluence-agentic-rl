import { useState, useRef, useEffect } from 'react';
import { JiraIcon, ConfluenceIcon } from '@atlaskit/logo';
import { useApp } from '../contexts/AppContext';
import type { ContextMode } from '../types';
import './ContextDropdown.css';

type ModeOption = 'jira' | 'confluence' | 'web';

interface ContextOption {
  mode: 'auto' | ModeOption;
  label: string;
  description: string;
  icon: JSX.Element;
}

const options: ContextOption[] = [
  {
    mode: 'auto',
    label: 'Auto',
    description: 'AI detects context',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/>
      </svg>
    ),
  },
  {
    mode: 'jira',
    label: 'Jira',
    description: 'Issues & projects',
    icon: <JiraIcon appearance="brand" size="small" />,
  },
  {
    mode: 'confluence',
    label: 'Confluence',
    description: 'Documentation',
    icon: <ConfluenceIcon appearance="brand" size="small" />,
  },
  {
    mode: 'web',
    label: 'Web Search',
    description: 'Search the internet',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <circle cx="12" cy="12" r="10"/>
        <line x1="2" y1="12" x2="22" y2="12"/>
        <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
      </svg>
    ),
  },
];

export function ContextDropdown() {
  const { contextMode, setContextMode } = useApp();
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const isAuto = contextMode === 'auto';
  const selectedModes = isAuto ? [] : (contextMode as ModeOption[]);

  // Get display text for button
  const getDisplayText = () => {
    if (isAuto) return 'Auto';
    if (selectedModes.length === 0) return 'Select Sources';
    if (selectedModes.length === 1) {
      const opt = options.find(o => o.mode === selectedModes[0]);
      return opt?.label || 'Select';
    }
    return `${selectedModes.length} Sources`;
  };

  // Get display icon for button
  const getDisplayIcon = () => {
    if (isAuto) return options[0].icon;
    if (selectedModes.length === 1) {
      const opt = options.find(o => o.mode === selectedModes[0]);
      return opt?.icon || options[0].icon;
    }
    return (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"/>
      </svg>
    );
  };

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  function toggleAuto() {
    setContextMode('auto');
  }

  function toggleMode(mode: ModeOption, e?: React.MouseEvent) {
    // Prevent checkbox from being clicked when clicking the button
    if (e) {
      e.preventDefault();
    }

    // If currently auto, switch to array with this mode
    if (isAuto) {
      setContextMode([mode]);
      return;
    }

    const modes = selectedModes as ModeOption[];
    const index = modes.indexOf(mode);
    
    if (index > -1) {
      // Remove the mode
      const newModes = modes.filter(m => m !== mode);
      // If no modes left, switch to auto
      setContextMode(newModes.length === 0 ? 'auto' : newModes);
    } else {
      // Add the mode
      setContextMode([...modes, mode]);
    }
  }

  function isChecked(mode: 'auto' | ModeOption): boolean {
    if (mode === 'auto') return isAuto;
    return !isAuto && selectedModes.includes(mode);
  }

  return (
    <div className="context-dropdown" ref={dropdownRef}>
      <button
        className={`context-dropdown-btn ${isOpen ? 'open' : ''}`}
        onClick={() => setIsOpen(!isOpen)}
      >
        <span className="mode-icon">{getDisplayIcon()}</span>
        <span className="mode-text">{getDisplayText()}</span>
        <svg className="dropdown-arrow" width="12" height="12" viewBox="0 0 12 12" fill="currentColor">
          <path d="M2 4L6 8L10 4H2Z"/>
        </svg>
      </button>

      {isOpen && (
        <div className="context-dropdown-menu">
          {/* Auto option with radio behavior */}
          <button
            className={`context-option ${isAuto ? 'active' : ''}`}
            onClick={toggleAuto}
          >
            <input
              type="radio"
              checked={isAuto}
              onChange={toggleAuto}
              className="option-checkbox"
            />
            <span className="option-icon">{options[0].icon}</span>
            <div className="option-content">
              <span className="option-label">{options[0].label}</span>
              <span className="option-desc">{options[0].description}</span>
            </div>
          </button>

          <div className="dropdown-divider" />

          {/* Multi-select options */}
          {options.slice(1).map((option) => (
            <button
              key={option.mode}
              className={`context-option ${isChecked(option.mode) ? 'active' : ''} ${isAuto ? 'auto-disabled' : ''}`}
              onClick={(e) => toggleMode(option.mode as ModeOption, e)}
            >
              <input
                type="checkbox"
                checked={isChecked(option.mode)}
                readOnly
                className="option-checkbox"
              />
              <span className="option-icon">{option.icon}</span>
              <div className="option-content">
                <span className="option-label">{option.label}</span>
                <span className="option-desc">{option.description}</span>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
