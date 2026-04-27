import { useState } from 'react';

interface TimerangePickerProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}

const PRESETS = [7, 30, 60, 90, 120, 240, 365] as const;

function formatDate(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}${month}${day}`;
}

function parseDate(str: string): Date | null {
  if (!str || str.length !== 8) return null;
  const year = parseInt(str.slice(0, 4));
  const month = parseInt(str.slice(4, 6)) - 1;
  const day = parseInt(str.slice(6, 8));
  const date = new Date(year, month, day);
  if (isNaN(date.getTime())) return null;
  return date;
}

export function TimerangePicker({ value, onChange, placeholder = '20240101-20241231' }: TimerangePickerProps) {
  const [isCustom, setIsCustom] = useState(false);

  // Parse current value
  const [startDateStr, endDateStr] = value.split('-');
  const startDate = parseDate(startDateStr || '');
  const endDate = parseDate(endDateStr || '');

  const handlePreset = (days: number) => {
    const end = new Date();
    const start = new Date();
    start.setDate(end.getDate() - days);
    
    const timerange = `${formatDate(start)}-${formatDate(end)}`;
    onChange(timerange);
    setIsCustom(false);
  };

  const handleStartDateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newStartDate = e.target.value; // YYYY-MM-DD
    const formatted = newStartDate.replace(/-/g, '');
    const newEndDate = endDateStr || formatDate(new Date());
    onChange(`${formatted}-${newEndDate}`);
    setIsCustom(true);
  };

  const handleEndDateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newEndDate = e.target.value; // YYYY-MM-DD
    const formatted = newEndDate.replace(/-/g, '');
    const newStartDate = startDateStr || formatDate(new Date());
    onChange(`${newStartDate}-${formatted}`);
    setIsCustom(true);
  };

  // Format dates for input type="date" (YYYY-MM-DD)
  const formatForInput = (date: Date | null): string => {
    if (!date) return '';
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  };

  return (
    <div className="timerange-picker">
      <div className="timerange-presets">
        {PRESETS.map((days) => (
          <button
            key={days}
            type="button"
            className={`chip ${!isCustom ? 'active' : ''}`}
            onClick={() => handlePreset(days)}
          >
            {days}d
          </button>
        ))}
        <button
          type="button"
          className={`chip ${isCustom ? 'active' : ''}`}
          onClick={() => setIsCustom(true)}
        >
          Custom
        </button>
      </div>
      
      {!isCustom ? (
        <input
          value={value}
          onChange={(e) => {
            onChange(e.target.value);
            setIsCustom(true);
          }}
          placeholder={placeholder}
        />
      ) : (
        <div className="timerange-dates">
          <label>
            Start Date
            <input
              type="date"
              value={formatForInput(startDate)}
              onChange={handleStartDateChange}
            />
          </label>
          <label>
            End Date
            <input
              type="date"
              value={formatForInput(endDate)}
              onChange={handleEndDateChange}
            />
          </label>
        </div>
      )}
    </div>
  );
}
