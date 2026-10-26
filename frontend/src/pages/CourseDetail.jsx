import React, { useState, useEffect, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import api from '../services/api';
import Navbar from '../components/Navbar';
import VideoPlayer from '../components/VideoPlayer';
import CitationBadge from '../components/CitationBadge';
import UploadLectureModal from '../components/UploadLectureModal';
import {
  ArrowLeft,
  Video,
  Upload,
  Sparkles,
  Send,
  Clock,
  CheckCircle2,
  Loader2,
  AlertTriangle,
  RotateCcw,
  Trash2,
  BookOpen,
  Plus,
  MessageSquare,
  History,
  X
} from 'lucide-react';

export default function CourseDetail() {
  const { courseId } = useParams();
  const { user, isProfessor } = useAuth();
  const videoPlayerRef = useRef(null);
  const chatBottomRef = useRef(null);
  const chatInputRef = useRef(null);

  const [course, setCourse] = useState(null);
  const [lectures, setLectures] = useState([]);
  const [selectedLecture, setSelectedLecture] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showUploadModal, setShowUploadModal] = useState(false);

  // Multi-session chat states
  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [showSessionsDrawer, setShowSessionsDrawer] = useState(false);
  const [loadingChat, setLoadingChat] = useState(false);

  const [query, setQuery] = useState('');
  const [messages, setMessages] = useState([]);
  const [streaming, setStreaming] = useState(false);

  const fetchCourseData = async () => {
    try {
      const [courseRes, lecturesRes] = await Promise.all([
        api.get(`/courses/${courseId}`),
        api.get(`/courses/${courseId}/lectures`)
      ]);

      setCourse(courseRes.data.data);
      const fetchedLectures = lecturesRes.data.data || [];
      setLectures(fetchedLectures);

      if (fetchedLectures.length > 0 && !selectedLecture) {
        setSelectedLecture(fetchedLectures[0]);
      }
    } catch (err) {
      console.error('Failed to load course details:', err);
    } finally {
      setLoading(false);
    }
  };

  // Fetch all chat sessions for this course
  const fetchConversations = async () => {
    try {
      const res = await api.get(`/courses/${courseId}/conversations`);
      const list = res.data.data || [];
      setConversations(list);
      return list;
    } catch (err) {
      console.warn('Could not load course conversations:', err);
      return [];
    }
  };

  // Switch to an existing chat session and load its history
  const loadConversation = async (convId) => {
    try {
      setLoadingChat(true);
      const res = await api.get(`/courses/${courseId}/conversations/${convId}`);
      const conv = res.data.data;
      if (conv) {
        setActiveConversationId(conv._id);
        if (conv.messages && conv.messages.length > 0) {
          setMessages(
            conv.messages.map((m) => ({
              sender: m.sender,
              text: m.text,
              citations: m.citations || []
            }))
          );
        } else {
          setMessages([
            {
              sender: 'assistant',
              text: `Started chat session: "${conv.title}". Ask anything about ${course?.code || 'this course'} lectures!`,
              citations: []
            }
          ]);
        }
      }
      setShowSessionsDrawer(false);
    } catch (err) {
      console.error('Failed to load conversation details:', err);
    } finally {
      setLoadingChat(false);
    }
  };

  // Start a fresh chat session with separate ID and state
  const handleStartNewChat = () => {
    setActiveConversationId(null);
    setMessages([
      {
        sender: 'assistant',
        text: `Hello! I am your course-grounded AI assistant for ${course?.code || 'this course'}. Ask me any questions about the lectures, and I will cite the exact video moments where the concepts were taught.`,
        citations: []
      }
    ]);
    setShowSessionsDrawer(false);
    if (chatInputRef.current) {
      chatInputRef.current.focus();
    }
  };

  // Delete a specific chat session
  const handleDeleteConversation = async (e, convId) => {
    e.stopPropagation();
    if (!window.confirm('Delete this chat session?')) return;

    try {
      await api.delete(`/courses/${courseId}/conversations/${convId}`);
      setConversations((prev) => prev.filter((c) => c._id !== convId));
      if (activeConversationId === convId) {
        handleStartNewChat();
      }
    } catch (err) {
      console.error('Failed to delete conversation:', err);
    }
  };

  useEffect(() => {
    fetchCourseData();
    fetchConversations().then((convs) => {
      if (convs && convs.length > 0) {
        loadConversation(convs[0]._id);
      } else {
        handleStartNewChat();
      }
    });
  }, [courseId]);

  // Polling for lecture processing status updates (every 5s if any lecture is processing or uploaded)
  useEffect(() => {
    const hasUnfinished = lectures.some((l) => l.status === 'processing' || l.status === 'uploaded');
    if (!hasUnfinished) return;

    const interval = setInterval(async () => {
      try {
        const res = await api.get(`/courses/${courseId}/lectures`);
        const updated = res.data.data || [];
        setLectures(updated);

        // Update selected lecture if its status changed
        if (selectedLecture) {
          const match = updated.find((l) => l._id === selectedLecture._id);
          if (match && match.status !== selectedLecture.status) {
            setSelectedLecture(match);
          }
        }
      } catch (e) {
        console.error('Polling error:', e);
      }
    }, 5000);

    return () => clearInterval(interval);
  }, [lectures, selectedLecture, courseId]);

  // Auto-scroll chat to bottom
  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streaming]);

  // Handle citation click: Seek video to cited timestamp
  const handleSeekCitation = (lectureId, startTime) => {
    if (lectureId && selectedLecture && lectureId !== selectedLecture._id) {
      const target = lectures.find((l) => l._id === lectureId);
      if (target) {
        setSelectedLecture(target);
      }
    }
    // Seek video player
    if (videoPlayerRef.current) {
      videoPlayerRef.current.seekTo(startTime, true);
    }
  };

  // Real-time SSE streaming chat dispatch
  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!query.trim() || streaming) return;

    const userText = query.trim();
    setQuery('');

    // Append student message
    const userMessage = { sender: 'student', text: userText, citations: [] };
    setMessages((prev) => [...prev, userMessage]);

    // Append empty placeholder for assistant streaming response
    setMessages((prev) => [
      ...prev,
      { sender: 'assistant', text: '', citations: [], isStreaming: true }
    ]);
    setStreaming(true);

    const token = localStorage.getItem('edumind_token');
    const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:5001/api/v1';

    try {
      const response = await fetch(`${apiBase}/courses/${courseId}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          query: userText,
          conversationId: activeConversationId
        })
      });

      if (!response.ok) {
        throw new Error(`Chat request failed with status: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let done = false;
      let accumulatedText = '';
      let accumulatedCitations = [];

      while (!done) {
        const { value, done: readerDone } = await reader.read();
        done = readerDone;
        if (value) {
          const chunkStr = decoder.decode(value, { stream: true });
          const lines = chunkStr.split('\n');

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const rawData = line.replace('data: ', '').trim();
              if (rawData === '[DONE]') {
                done = true;
                break;
              }
              try {
                const event = JSON.parse(rawData);

                // Handle session initialization event from backend
                if (event.conversationId) {
                  setActiveConversationId(event.conversationId);
                  fetchConversations();
                }

                if (event.token) {
                  accumulatedText += event.token;
                  setMessages((prev) => {
                    const next = [...prev];
                    const target = next[next.length - 1];
                    if (target && target.sender === 'assistant') {
                      target.text = accumulatedText;
                    }
                    return next;
                  });
                }
                if (event.citations && Array.isArray(event.citations)) {
                  accumulatedCitations = event.citations.map((c) => ({
                    lectureId: c.lecture_id,
                    lectureTitle: c.lecture_title,
                    startTime: c.start_time,
                    endTime: c.end_time,
                    chunkText: c.chunk_text
                  }));
                  setMessages((prev) => {
                    const next = [...prev];
                    const target = next[next.length - 1];
                    if (target && target.sender === 'assistant') {
                      target.citations = accumulatedCitations;
                    }
                    return next;
                  });
                }
              } catch (parseErr) {
                // Ignore chunk parsing non-json anomalies
              }
            }
          }
        }
      }
    } catch (err) {
      console.error('Streaming Chat Error:', err);
      setMessages((prev) => {
        const next = [...prev];
        const target = next[next.length - 1];
        if (target && target.sender === 'assistant') {
          target.text = `I encountered an error retrieving answers: ${err.message}. Please verify the AI service is active.`;
        }
        return next;
      });
    } finally {
      setStreaming(false);
      setMessages((prev) => {
        const next = [...prev];
        const target = next[next.length - 1];
        if (target) target.isStreaming = false;
        return next;
      });
      // Refresh conversation list after response finishes
      fetchConversations();
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="w-8 h-8 text-indigo-500 animate-spin" />
          <span className="text-xs font-semibold text-slate-400">Loading course materials...</span>
        </div>
      </div>
    );
  }

  const activeChatTitle = activeConversationId
    ? conversations.find((c) => c._id === activeConversationId)?.title || 'Active Chat Session'
    : 'New Chat';

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col text-slate-100">
      <Navbar />

      {/* Course Subheader */}
      <div className="bg-slate-900/80 backdrop-blur-md border-b border-slate-800/80 py-3.5 px-4 sm:px-6 lg:px-8 sticky top-16 z-20">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link
              to="/dashboard"
              className="p-1.5 rounded-xl text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
            >
              <ArrowLeft className="w-5 h-5" />
            </Link>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold px-2 py-0.5 rounded-md bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                  {course?.code}
                </span>
                <h1 className="text-base font-bold text-white tracking-tight">{course?.title}</h1>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Instructor: <span className="text-slate-300 font-medium">{course?.professor?.name}</span> •{' '}
                {lectures.length} {lectures.length === 1 ? 'Lecture' : 'Lectures'} Available
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            {!isProfessor && (
              <Link
                to={`/courses/${courseId}/buddy`}
                className="inline-flex items-center gap-2 px-3.5 py-2 bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 hover:from-indigo-600 hover:via-purple-600 hover:to-pink-600 text-white text-xs font-semibold rounded-xl shadow-md shadow-indigo-500/25 hover:shadow-indigo-500/40 transition-all cursor-pointer group active:scale-95"
                title="Open Buddy - AI Course Assistant (Gemini style)"
              >
                <Sparkles className="w-4 h-4 animate-pulse text-amber-300" />
                <span>Open Buddy</span>
              </Link>
            )}

            {isProfessor && (
              <button
                onClick={() => setShowUploadModal(true)}
                className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-xl shadow-md hover:shadow-indigo-500/20 transition-all cursor-pointer"
              >
                <Upload className="w-4 h-4" />
                <span>Upload Lecture</span>
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Main Layout */}
      <div className={`flex-1 w-full mx-auto p-4 sm:p-6 lg:p-8 ${isProfessor ? 'max-w-5xl' : 'max-w-7xl grid grid-cols-1 lg:grid-cols-12 gap-6'}`}>
        {/* Left Column: Video Player & Lecture Playlist */}
        <div className={`${isProfessor ? 'w-full' : 'lg:col-span-7'} flex flex-col gap-5`}>
          {/* Synchronized Video Player */}
          <VideoPlayer ref={videoPlayerRef} selectedLecture={selectedLecture} />

          {/* Lecture Playlist */}
          <div className="bg-slate-900/60 rounded-2xl border border-slate-800 p-5 shadow-sm">
            <div className="flex items-center justify-between mb-3.5">
              <h2 className="text-sm font-bold text-white flex items-center gap-2">
                <BookOpen className="w-4 h-4 text-indigo-400" />
                <span>Recorded Lectures</span>
              </h2>
              <span className="text-xs text-slate-400 font-mono">{lectures.length} total</span>
            </div>

            {lectures.length === 0 ? (
              <div className="text-center py-10 text-xs text-slate-500 border border-dashed border-slate-800 rounded-xl">
                No lectures uploaded yet for this course.
                {isProfessor && (
                  <button
                    onClick={() => setShowUploadModal(true)}
                    className="block mx-auto mt-2 text-indigo-400 hover:underline font-semibold"
                  >
                    Upload first lecture recording
                  </button>
                )}
              </div>
            ) : (
              <div className="space-y-2 max-h-[300px] overflow-y-auto pr-1">
                {lectures.map((lecture, idx) => {
                  const isSelected = selectedLecture?._id === lecture._id;
                  return (
                    <div
                      key={lecture._id}
                      onClick={() => setSelectedLecture(lecture)}
                      className={`flex items-center justify-between p-3 rounded-xl cursor-pointer border transition-all ${
                        isSelected
                          ? 'border-indigo-500/60 bg-indigo-500/10 shadow-xs'
                          : 'border-slate-800/80 hover:border-slate-700 bg-slate-900/40 hover:bg-slate-900/80'
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <span className="w-6 text-center text-xs font-bold text-slate-500">
                          {idx + 1}
                        </span>
                        <div>
                          <h4 className="text-xs font-semibold text-slate-200 line-clamp-1">
                            {lecture.title}
                          </h4>
                          <span className="text-[11px] text-slate-400 flex items-center gap-1 mt-0.5">
                            <Clock className="w-3 h-3 text-slate-500" /> {lecture.duration || 0}s
                          </span>
                        </div>
                      </div>

                      {/* Ingestion Status Badges */}
                      <div>
                        {lecture.status === 'processed' && (
                          <span className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                            <CheckCircle2 className="w-3 h-3" /> Ready
                          </span>
                        )}
                        {lecture.status === 'processing' && (
                          <span className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20 animate-pulse">
                            <Loader2 className="w-3 h-3 animate-spin" /> Processing
                          </span>
                        )}
                        {lecture.status === 'uploaded' && (
                          <span className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20">
                            Uploaded
                          </span>
                        )}
                        {lecture.status === 'failed' && (
                          <span className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-red-500/10 text-red-400 border border-red-500/20">
                            <AlertTriangle className="w-3 h-3" /> Failed
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Course-Specific RAG Chatbot (Students Only) */}
        {!isProfessor && (
          <div className="lg:col-span-5 bg-slate-900/60 rounded-2xl border border-slate-800 shadow-xl flex flex-col h-[760px] overflow-hidden relative">
            {/* Chat Header */}
            <div className="p-3.5 border-b border-slate-800/80 bg-slate-900/95 backdrop-blur-md flex flex-col gap-2 relative z-10">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-7 h-7 rounded-lg bg-gradient-to-tr from-indigo-600 to-violet-500 text-white flex items-center justify-center shadow-md">
                  <Sparkles className="w-3.5 h-3.5" />
                </div>
                <div>
                  <h3 className="text-xs font-bold text-white leading-tight">Course AI Assistant</h3>
                  <p className="text-[10px] text-slate-400 font-medium">Grounded in lecture transcripts</p>
                </div>
              </div>

              <div className="flex items-center gap-1.5">
                {/* Expand to Buddy View Button */}
                <Link
                  to={`/courses/${courseId}/buddy`}
                  className="inline-flex items-center gap-1 px-2.5 py-1 text-[11px] font-semibold text-white bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 rounded-lg shadow-xs transition-all cursor-pointer active:scale-95"
                  title="Open full Gemini-style Buddy chat page"
                >
                  <Sparkles className="w-3 h-3 text-amber-300" />
                  <span>Open Buddy</span>
                </Link>

                {/* + New Chat Button */}
                <button
                  onClick={handleStartNewChat}
                  className="inline-flex items-center gap-1 px-2.5 py-1 text-[11px] font-semibold text-indigo-300 bg-indigo-500/15 hover:bg-indigo-500/25 border border-indigo-500/30 rounded-lg transition-all cursor-pointer shadow-xs active:scale-95"
                  title="Create a new independent chat session"
                >
                  <Plus className="w-3.5 h-3.5 text-indigo-400" />
                  <span>New Chat</span>
                </button>

                {/* History Drawer Toggle Button */}
                <button
                  onClick={() => setShowSessionsDrawer(!showSessionsDrawer)}
                  className={`inline-flex items-center gap-1 px-2.5 py-1 text-[11px] font-medium rounded-lg border transition-all cursor-pointer ${
                    showSessionsDrawer
                      ? 'bg-slate-800 text-white border-slate-700'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/70 border-slate-800'
                  }`}
                  title="View past chat sessions"
                >
                  <History className="w-3.5 h-3.5" />
                  <span className="text-[10px] bg-slate-800 px-1.5 py-0.5 rounded-full border border-slate-700 font-mono">
                    {conversations.length}
                  </span>
                </button>
              </div>
            </div>

            {/* Active Session Info Bar */}
            <div className="flex items-center justify-between text-[11px] px-1 text-slate-400 pt-0.5">
              <div className="flex items-center gap-1.5 truncate max-w-[280px]">
                <MessageSquare className="w-3 h-3 text-indigo-400 shrink-0" />
                <span className="truncate text-slate-300 font-medium">
                  {activeChatTitle}
                </span>
              </div>
              <span className="text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                Online
              </span>
            </div>

            {/* Chat Sessions History Dropdown / Drawer */}
            {showSessionsDrawer && (
              <div className="absolute top-full left-0 right-0 z-30 bg-slate-900 border-b border-x border-slate-800 rounded-b-2xl shadow-2xl p-3 max-h-[340px] overflow-y-auto space-y-2 backdrop-blur-xl">
                <div className="flex items-center justify-between pb-2 border-b border-slate-800/80 px-1">
                  <span className="text-[11px] font-bold text-slate-300 uppercase tracking-wider">
                    Past Chats ({conversations.length})
                  </span>
                  <button
                    onClick={() => setShowSessionsDrawer(false)}
                    className="p-1 text-slate-400 hover:text-white rounded hover:bg-slate-800 cursor-pointer"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>

                {conversations.length === 0 ? (
                  <div className="text-center py-6 text-[11px] text-slate-500">
                    No past chat sessions yet. Ask a question to start one!
                  </div>
                ) : (
                  <div className="space-y-1.5">
                    {conversations.map((conv) => {
                      const isActive = conv._id === activeConversationId;
                      return (
                        <div
                          key={conv._id}
                          onClick={() => loadConversation(conv._id)}
                          className={`group flex items-center justify-between p-2.5 rounded-xl cursor-pointer border transition-all ${
                            isActive
                              ? 'bg-indigo-600/20 border-indigo-500/50 text-white shadow-xs'
                              : 'bg-slate-800/40 hover:bg-slate-800 border-slate-800/80 hover:border-slate-700 text-slate-300'
                          }`}
                        >
                          <div className="flex items-start gap-2.5 truncate pr-2">
                            <MessageSquare
                              className={`w-3.5 h-3.5 mt-0.5 shrink-0 ${
                                isActive ? 'text-indigo-400' : 'text-slate-500'
                              }`}
                            />
                            <div className="truncate text-left">
                              <p className="text-xs font-medium truncate">{conv.title || 'Untitled Chat'}</p>
                              <div className="flex items-center gap-2 mt-0.5 text-[10px] text-slate-400">
                                <span>{new Date(conv.updatedAt || conv.createdAt).toLocaleDateString([], { month: 'short', day: 'numeric' })}</span>
                                <span>•</span>
                                <span>{conv.messageCount || 0} messages</span>
                              </div>
                            </div>
                          </div>

                          <button
                            onClick={(e) => handleDeleteConversation(e, conv._id)}
                            className="opacity-0 group-hover:opacity-100 p-1 text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 rounded-lg transition-all cursor-pointer"
                            title="Delete this chat session"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Chat Messages Body */}
          <div className="flex-1 p-4 overflow-y-auto space-y-4 text-xs">
            {loadingChat ? (
              <div className="flex flex-col items-center justify-center h-full text-slate-400 gap-2">
                <Loader2 className="w-6 h-6 animate-spin text-indigo-400" />
                <span className="text-xs">Loading chat session memory...</span>
              </div>
            ) : (
              messages.map((msg, i) => (
                <div
                  key={i}
                  className={`flex flex-col ${
                    msg.sender === 'student' ? 'items-end' : 'items-start'
                  }`}
                >
                  <div
                    className={`max-w-[88%] rounded-2xl px-4 py-3 leading-relaxed whitespace-pre-wrap ${
                      msg.sender === 'student'
                        ? 'bg-indigo-600 text-white rounded-br-xs shadow-md'
                        : 'bg-slate-800/90 text-slate-200 rounded-bl-xs border border-slate-700/60 shadow-sm'
                    }`}
                  >
                    {msg.text || (msg.isStreaming ? '...' : '')}
                  </div>

                  {/* Clickable Timestamp Citations */}
                  {msg.citations && msg.citations.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1.5 max-w-[88%]">
                      {msg.citations.map((cite, cIdx) => (
                        <CitationBadge
                          key={cIdx}
                          citation={cite}
                          onSeek={handleSeekCitation}
                        />
                      ))}
                    </div>
                  )}
                </div>
              ))
            )}

            {streaming && (
              <div className="flex items-center gap-2 text-xs text-slate-400 italic pl-1">
                <Loader2 className="w-3.5 h-3.5 animate-spin text-indigo-400" />
                <span>Synthesizing grounded answer with citations...</span>
              </div>
            )}
            <div ref={chatBottomRef} />
          </div>

          {/* Chat Input Bar */}
          <form onSubmit={handleSendMessage} className="p-3 border-t border-slate-800 bg-slate-900/90">
            <div className="relative flex items-center">
              <input
                ref={chatInputRef}
                type="text"
                disabled={streaming || loadingChat}
                placeholder={`Ask anything about ${course?.code || 'this course'} lectures...`}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="w-full text-xs py-2.5 pl-3.5 pr-11 bg-slate-800/70 border border-slate-700/80 text-white rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/40 focus:border-indigo-500 transition-all placeholder:text-slate-500 disabled:opacity-50"
              />
              <button
                type="submit"
                disabled={!query.trim() || streaming || loadingChat}
                className="absolute right-1.5 p-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg disabled:opacity-40 transition-all shadow-sm cursor-pointer active:scale-95"
              >
                <Send className="w-3.5 h-3.5" />
              </button>
            </div>
            <p className="text-[10px] text-slate-500 text-center mt-2">
              Edumind AI grounds answers in professor recordings. Click badges to jump to video moments.
            </p>
          </form>
        </div>
        )}
      </div>

      {/* Upload Modal (Professor Only) */}
      {isProfessor && (
        <UploadLectureModal
          isOpen={showUploadModal}
          onClose={() => setShowUploadModal(false)}
          courseId={courseId}
          onLectureUploaded={() => {
            fetchCourseData();
          }}
        />
      )}
    </div>
  );
}
