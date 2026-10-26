import React, { useRef, useImperativeHandle, forwardRef, useState } from 'react';
import { PlayCircle, Clock, Video, Loader2, Sparkles } from 'lucide-react';

const formatSeconds = (sec) => {
  if (!sec || isNaN(sec)) return '00:00';
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
};

const VideoPlayer = forwardRef(({ selectedLecture }, ref) => {
  const videoRef = useRef(null);
  const [seekNotification, setSeekNotification] = useState(null);

  // Expose seekTo method to parent component
  useImperativeHandle(ref, () => ({
    seekTo: (seconds, shouldPlay = true) => {
      if (videoRef.current) {
        videoRef.current.currentTime = seconds;
        if (shouldPlay) {
          videoRef.current.play().catch(() => {});
        }
        setSeekNotification(`Jumped to ${formatSeconds(seconds)}`);
        setTimeout(() => setSeekNotification(null), 2500);
      }
    }
  }));

  const hasVideo = selectedLecture && selectedLecture.cloudinaryUrl;

  return (
    <div className="relative bg-slate-950 rounded-2xl overflow-hidden shadow-xl aspect-video flex flex-col items-center justify-center border border-slate-800">
      {hasVideo ? (
        <>
          <video
            ref={videoRef}
            src={selectedLecture.cloudinaryUrl}
            controls
            playsInline
            className="w-full h-full object-contain bg-black"
          />

          {/* Seek Feedback Banner */}
          {seekNotification && (
            <div className="absolute top-4 right-4 bg-indigo-600/90 backdrop-blur-md text-white text-xs font-semibold px-3 py-1.5 rounded-full shadow-lg flex items-center gap-1.5 animate-bounce">
              <Sparkles className="w-3.5 h-3.5 text-amber-300" />
              <span>{seekNotification}</span>
            </div>
          )}

          {/* Header Overlay info */}
          <div className="absolute top-0 left-0 right-0 p-3 bg-gradient-to-b from-black/70 via-black/30 to-transparent opacity-0 hover:opacity-100 transition-opacity pointer-events-none flex items-center justify-between text-white text-xs">
            <span className="font-semibold truncate max-w-md">{selectedLecture.title}</span>
            {selectedLecture.duration > 0 && (
              <span className="font-mono text-[11px] opacity-80">{formatSeconds(selectedLecture.duration)}</span>
            )}
          </div>
        </>
      ) : (
        <div className="text-center p-8 max-w-sm">
          <div className="w-16 h-16 rounded-2xl bg-slate-900 border border-slate-800 flex items-center justify-center mx-auto mb-4 text-slate-500 shadow-inner">
            <PlayCircle className="w-8 h-8" />
          </div>
          <h3 className="text-sm font-semibold text-slate-200">
            {selectedLecture ? selectedLecture.title : 'No Lecture Selected'}
          </h3>
          <p className="text-xs text-slate-400 mt-1.5 leading-relaxed">
            {selectedLecture?.status === 'processing'
              ? 'This lecture is currently being transcribed and indexed by Edumind AI.'
              : 'Select a recorded lecture from the playlist or upload a new lecture video.'}
          </p>
        </div>
      )}
    </div>
  );
});

VideoPlayer.displayName = 'VideoPlayer';
export default VideoPlayer;
