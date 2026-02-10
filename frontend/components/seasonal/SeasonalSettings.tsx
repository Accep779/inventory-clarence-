'use client';

import React, { useState } from 'react';

interface SeasonConfig {
  name: string;
  enabled: boolean;
  startMonth: number;
  endMonth: number;
  keywords: string[];
}

interface SeasonalSettingsProps {
  onSave?: (settings: any) => void;
  initialSettings?: {
    scanFrequency: 'daily' | 'weekly' | 'monthly';
    seasons: SeasonConfig[];
    autoPropose: boolean;
    riskThreshold: 'low' | 'moderate' | 'high' | 'critical';
  };
}

const defaultSeasons: SeasonConfig[] = [
  { name: 'Spring', enabled: true, startMonth: 3, endMonth: 6, keywords: ['spring', 'easter', 'floral'] },
  { name: 'Summer', enabled: true, startMonth: 6, endMonth: 9, keywords: ['summer', 'beach', 'swim', 'outdoor'] },
  { name: 'Fall', enabled: true, startMonth: 9, endMonth: 12, keywords: ['fall', 'autumn', 'halloween', 'thanksgiving'] },
  { name: 'Winter', enabled: true, startMonth: 12, endMonth: 3, keywords: ['winter', 'christmas', 'holiday', 'snow'] },
  { name: 'Back to School', enabled: true, startMonth: 7, endMonth: 9, keywords: ['school', 'backpack', 'supplies'] },
];

export function SeasonalSettings({ onSave, initialSettings }: SeasonalSettingsProps) {
  const [scanFrequency, setScanFrequency] = useState(initialSettings?.scanFrequency || 'weekly');
  const [autoPropose, setAutoPropose] = useState(initialSettings?.autoPropose ?? false);
  const [riskThreshold, setRiskThreshold] = useState(initialSettings?.riskThreshold || 'moderate');
  const [seasons, setSeasons] = useState<SeasonConfig[]>(initialSettings?.seasons || defaultSeasons);
  const [isSaving, setIsSaving] = useState(false);

  const toggleSeason = (index: number) => {
    const updated = [...seasons];
    updated[index] = { ...updated[index], enabled: !updated[index].enabled };
    setSeasons(updated);
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await onSave?.({
        scanFrequency,
        autoPropose,
        riskThreshold,
        seasons
      });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Scan Frequency */}
      <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
        <h3 className="text-lg font-semibold text-white mb-4">⏰ Scan Frequency</h3>
        
        <div className="flex gap-3">
          {(['daily', 'weekly', 'monthly'] as const).map((freq) => (
            <button
              key={freq}
              onClick={() => setScanFrequency(freq)}
              className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                scanFrequency === freq
                  ? 'bg-indigo-600 text-white'
                  : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
              }`}
            >
              {freq.charAt(0).toUpperCase() + freq.slice(1)}
            </button>
          ))}
        </div>
        
        <p className="mt-3 text-sm text-gray-400">
          {scanFrequency === 'daily' && 'Products will be scanned every day for seasonal risks.'}
          {scanFrequency === 'weekly' && 'Products will be scanned every Sunday for seasonal risks.'}
          {scanFrequency === 'monthly' && 'Products will be scanned on the 1st of each month.'}
        </p>
      </div>

      {/* Risk Threshold */}
      <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
        <h3 className="text-lg font-semibold text-white mb-4">🎯 Alert Threshold</h3>
        
        <div className="flex gap-3">
          {(['critical', 'high', 'moderate', 'low'] as const).map((level) => (
            <button
              key={level}
              onClick={() => setRiskThreshold(level)}
              className={`px-4 py-2 rounded-lg font-medium transition-colors capitalize ${
                riskThreshold === level
                  ? level === 'critical' ? 'bg-red-600 text-white'
                  : level === 'high' ? 'bg-orange-600 text-white'
                  : level === 'moderate' ? 'bg-yellow-600 text-white'
                  : 'bg-green-600 text-white'
                  : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
              }`}
            >
              {level}
            </button>
          ))}
        </div>
        
        <p className="mt-3 text-sm text-gray-400">
          Only products at or above this risk level will trigger alerts.
        </p>
      </div>

      {/* Season Configuration */}
      <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
        <h3 className="text-lg font-semibold text-white mb-4">🗓️ Active Seasons</h3>
        
        <div className="space-y-3">
          {seasons.map((season, index) => (
            <div
              key={season.name}
              className={`flex items-center justify-between p-4 rounded-lg transition-colors ${
                season.enabled ? 'bg-gray-800' : 'bg-gray-800/50'
              }`}
            >
              <div className="flex items-center gap-3">
                <button
                  onClick={() => toggleSeason(index)}
                  className={`w-10 h-6 rounded-full transition-colors relative ${
                    season.enabled ? 'bg-indigo-600' : 'bg-gray-600'
                  }`}
                >
                  <span
                    className={`absolute top-1 w-4 h-4 bg-white rounded-full transition-transform ${
                      season.enabled ? 'left-5' : 'left-1'
                    }`}
                  />
                </button>
                <span className={season.enabled ? 'text-white' : 'text-gray-500'}>
                  {season.name}
                </span>
              </div>
              
              <div className="text-sm text-gray-400">
                {season.keywords.slice(0, 3).join(', ')}
                {season.keywords.length > 3 && ` +${season.keywords.length - 3} more`}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Auto Propose */}
      <div className="bg-gray-900 rounded-xl p-6 border border-gray-800">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-white">🤖 Auto-Propose Clearance</h3>
            <p className="text-sm text-gray-400 mt-1">
              Automatically create inbox proposals for high-risk seasonal products
            </p>
          </div>
          
          <button
            onClick={() => setAutoPropose(!autoPropose)}
            className={`w-12 h-7 rounded-full transition-colors relative ${
              autoPropose ? 'bg-indigo-600' : 'bg-gray-600'
            }`}
          >
            <span
              className={`absolute top-1 w-5 h-5 bg-white rounded-full transition-transform ${
                autoPropose ? 'left-6' : 'left-1'
              }`}
            />
          </button>
        </div>
      </div>

      {/* Save Button */}
      <button
        onClick={handleSave}
        disabled={isSaving}
        className="w-full py-3 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 rounded-xl text-white font-semibold transition-colors"
      >
        {isSaving ? 'Saving...' : 'Save Settings'}
      </button>
    </div>
  );
}

export default SeasonalSettings;
