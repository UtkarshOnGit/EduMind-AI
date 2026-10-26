import React from 'react';
import { Play, Video } from 'lucide-react';

/**
 * Format seconds into MM:SS
 */
const formatSeconds = (sec) => {
  if (sec === undefined || sec === null || isNaN(sec)) return '00:00';
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
};

export default function CitationBadge({ citation, onSeek }) {
  if (!citation) return null;

  const title = citation.lectureTitle || 'Lecture';
  const startTime = citation.startTime || 0;
  const timeFormatted = formatSeconds(startTime);

  const handleClick = () => {
    if (onSeek) {
      onSeek(citation.lectureId, startTime);
    }
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      title={citation.chunkText ? `Citation: "${citation.chunkText}"` : `Jump to ${title} at ${timeFormatted}`}
      className="inline-flex items-center gap-1.5 px-2.5 py-1 text-[11px] font-medium rounded-lg bg-indigo-50/90 hover:bg-indigo-100 text-indigo-700 hover:text-indigo-900 border border-indigo-200/80 shadow-xs transition-all hover:scale-[1.02] active:scale-[0.98] cursor-pointer group"
    >
      <span className="flex items-center justify-center w-3.5 h-3.5 rounded-full bg-indigo-600 text-white group-hover:bg-indigo-700 transition-colors">
        <Play className="w-2 h-2 fill-current ml-0.5" />
      </span>
      <span className="truncate max-w-[140px] font-semibold">{title}</span>
      <span className="text-indigo-500 font-mono text-[10px]">@{timeFormatted}</span>
    </button>
  );
}
