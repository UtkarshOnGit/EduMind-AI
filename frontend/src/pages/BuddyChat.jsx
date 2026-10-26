import React, { useState, useEffect, useRef } from 'react';
import { useParams, Link, useNavigate, Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import api from '../services/api';
import VideoPlayer from '../components/VideoPlayer';
import CitationBadge from '../components/CitationBadge';
import {
  Sparkles,
  Send,
  Plus,
  MessageSquare,
  Trash2,
  ArrowLeft,
  Loader2,
  Play,
  X,
  Menu,
  ChevronRight,
  BookOpen,
  Clock,
  Lightbulb,
  CheckCircle2
} from 'lucide-react';

/**
 * Format relative time for conversation list
 */
const formatRelativeTime = (dateString) => {
  if (!dateString) return 'Recently';
  const now = new Date();
  const date = new Date(dateString);
  const diffInMinutes = Math.floor((now - date) / (1000 * 60));

  if (diffInMinutes < 1) return 'Just now';
  if (diffInMinutes < 60) return `${diffInMinutes}m ago`;
  const diffInHours = Math.floor(diffInMinutes / 60);
  if (diffInHours < 24) return `${diffInHours}h ago`;
  const diffInDays = Math.floor(diffInHours / 24);
  if (diffInDays === 1) return 'Yesterday';
  if (diffInDays < 7) return `${diffInDays}d ago`;
  return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
};

/**
 * Formats seconds into MM:SS
 */
const formatSeconds = (sec) => {
  if (!sec || isNaN(sec)) return '00:00';
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
};

export default function BuddyChat() {
  const { courseId } = useParams();
  const { user, isProfessor } = useAuth();
  const navigate = useNavigate();

  // Buddy chatbot is currently student-only
  if (isProfessor) {
    return <Navigate to={`/courses/${courseId}`} replace />;
  }

  const chatBottomRef = useRef(null);
  const inputRef = useRef(null);
  const modalVideoRef = useRef(null);

  const [course, setCourse] = useState(null);
  const [lectures, setLectures] = useState([]);
  const [loadingCourse, setLoadingCourse] = useState(true);

  // Sidebar state
  const [sidebarOpen, setSidebarOpen] = useState(true);

  // Conversations state (sorted by updatedAt descending)
  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [loadingMessages, setLoadingMessages] = useState(false);

  // Query & Streaming state
  const [query, setQuery] = useState('');
  const [streaming, setStreaming] = useState(false);

  // Video Citation Modal state
  const [activeCitationVideo, setActiveCitationVideo] = useState(null);

  // 1. Fetch course details and lectures list
  useEffect(() => {
    const fetchCourseAndLectures = async () => {
      try {
        const [courseRes, lecturesRes] = await Promise.all([
          api.get(`/courses/${courseId}`),
          api.get(`/courses/${courseId}/lectures`)
        ]);
        setCourse(courseRes.data.data);
        setLectures(lecturesRes.data.data || []);
      } catch (err) {
        console.error('Failed to load course details:', err);
      } finally {
        setLoadingCourse(false);
      }
    };

    fetchCourseAndLectures();
  }, [courseId]);

  // 2. Fetch conversations list for this course (sorted by last updated time)
  const fetchConversations = async (autoSelectId = null) => {
    try {
      const res = await api.get(`/courses/${courseId}/conversations`);
      const list = res.data.data || [];
      // Sort descending by updatedAt
      list.sort((a, b) => new Date(b.updatedAt || b.createdAt) - new Date(a.updatedAt || a.createdAt));
      setConversations(list);

      if (autoSelectId) {
        loadConversation(autoSelectId);
      } else if (!activeConversationId && list.length > 0) {
        loadConversation(list[0]._id);
      }
      return list;
    } catch (err) {
      console.warn('Could not fetch conversations:', err);
      return [];
    }
  };

  useEffect(() => {
    fetchConversations();
  }, [courseId]);

  // 3. Load full message history of a selected conversation
  const loadConversation = async (convId) => {
    if (streaming) return;
    try {
      setLoadingMessages(true);
      const res = await api.get(`/courses/${courseId}/conversations/${convId}`);
      const conv = res.data.data;
      if (conv) {
        setActiveConversationId(conv._id);
        setMessages(
          (conv.messages || []).map((m) => ({
            sender: m.sender,
            text: m.text,
            citations: m.citations || []
          }))
        );
      }
    } catch (err) {
      console.error('Failed to load conversation history:', err);
    } finally {
      setLoadingMessages(false);
    }
  };

  // 4. Start a brand new chat session (Gemini style)
  const handleStartNewChat = () => {
    if (streaming) return;
    setActiveConversationId(null);
    setMessages([]);
    setQuery('');
    if (inputRef.current) {
      inputRef.current.focus();
    }
  };

  // 5. Delete a specific conversation session
  const handleDeleteConversation = async (e, convId) => {
    e.stopPropagation();
    if (!window.confirm('Delete this chat session from Buddy?')) return;

    try {
      await api.delete(`/courses/${courseId}/conversations/${convId}`);
      const updatedList = conversations.filter((c) => c._id !== convId);
      setConversations(updatedList);

      if (activeConversationId === convId) {
        if (updatedList.length > 0) {
          loadConversation(updatedList[0]._id);
        } else {
          handleStartNewChat();
        }
      }
    } catch (err) {
      console.error('Failed to delete conversation:', err);
    }
  };

  // Auto-scroll to bottom of chat
  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streaming]);

  // Handle citation badge click: open video preview modal at the exact timestamp
  const handleOpenCitationVideo = (lectureId, startTime, chunkText, lectureTitle) => {
    let targetLecture = lectures.find((l) => l._id === lectureId);
    if (!targetLecture && lectures.length > 0) {
      targetLecture = lectures[0];
    }

    if (targetLecture) {
      setActiveCitationVideo({
        lecture: targetLecture,
        startTime,
        chunkText,
        lectureTitle: lectureTitle || targetLecture.title
      });
    }
  };

  // When citation video modal opens, seek to timestamp
  useEffect(() => {
    if (activeCitationVideo && modalVideoRef.current) {
      setTimeout(() => {
        modalVideoRef.current.seekTo(activeCitationVideo.startTime, true);
      }, 200);
    }
  }, [activeCitationVideo]);

  // 6. Real-time streaming chat dispatch
  const handleSendMessage = async (textToSend = null) => {
    const text = (textToSend || query).trim();
    if (!text || streaming) return;

    setQuery('');

    // Append student message
    const userMessage = { sender: 'student', text, citations: [] };
    setMessages((prev) => [...prev, userMessage]);

    // Append placeholder for assistant streaming response
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
          query: text,
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

                // Receive newly created conversation ID from backend
                if (event.conversationId) {
                  setActiveConversationId(event.conversationId);
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
              } catch (e) {
                // Ignore non-json stream lines
              }
            }
          }
        }
      }
    } catch (err) {
      console.error('Buddy Streaming Error:', err);
      setMessages((prev) => {
        const next = [...prev];
        const target = next[next.length - 1];
        if (target && target.sender === 'assistant') {
          target.text = `Buddy encountered an issue retrieving answers: ${err.message}. Please check that the AI service is online.`;
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
      // Refresh conversations list in background to display new title & updated timestamp
      fetchConversations();
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  // Suggestion prompt cards for empty chat (Gemini style)
  const suggestionCards = [
    {
      title: 'Dynamic Programming Core',
      prompt: 'What is Dynamic Programming and what core problem does it solve?',
      icon: '💡'
    },
    {
      title: 'Memoization vs Tabulation',
      prompt: 'Compare top-down memoization and bottom-up tabulation with pros and cons.',
      icon: '⚡'
    },
    {
      title: 'Optimal Substructure',
      prompt: 'What is optimal substructure and how is it identified in algorithms?',
      icon: '🎯'
    },
    {
      title: 'Lecture 1 Key Takeaways',
      prompt: 'Summarize the primary takeaways and principles taught in Lecture 1.',
      icon: '📝'
    }
  ];

  if (loadingCourse) {
    return (
      <div className="h-screen bg-slate-950 flex items-center justify-center text-slate-400">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="w-8 h-8 text-indigo-500 animate-spin" />
          <span className="text-xs font-semibold">Opening Buddy...</span>
        </div>
      </div>
    );
  }

  const activeChat = conversations.find((c) => c._id === activeConversationId);

  return (
    <div className="h-screen w-screen bg-[#090d16] text-slate-100 flex overflow-hidden font-sans">
      {/* ============================================================ */}
      {/* LEFT SECTION: PREVIOUS CHATS SORTED BY LAST UPDATE TIME     */}
      {/* ============================================================ */}
      <aside
        className={`${
          sidebarOpen ? 'w-72 sm:w-80' : 'w-0 -translate-x-full'
        } transition-all duration-300 ease-in-out h-full bg-[#0d1322] border-r border-slate-800/80 flex flex-col shrink-0 z-30 select-none overflow-hidden`}
      >
        {/* Sidebar Header */}
        <div className="p-4 border-b border-slate-800/60 flex items-center justify-between">
          <Link
            to={`/courses/${courseId}`}
            className="flex items-center gap-2 text-xs font-semibold text-slate-400 hover:text-white transition-colors group"
            title="Return to Course"
          >
            <ArrowLeft className="w-4 h-4 text-slate-500 group-hover:text-indigo-400 transition-colors" />
            <span className="truncate max-w-[170px]">{course?.code || 'Course'}</span>
          </Link>

          <button
            onClick={() => setSidebarOpen(false)}
            className="p-1 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800/80 transition-colors sm:hidden"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Gemini-style "+ New chat" Button */}
        <div className="p-3">
          <button
            onClick={handleStartNewChat}
            className="w-full flex items-center gap-3 px-4 py-3 bg-slate-800/70 hover:bg-slate-800 text-slate-200 hover:text-white rounded-2xl border border-slate-700/60 hover:border-indigo-500/50 shadow-sm transition-all cursor-pointer group active:scale-[0.99]"
          >
            <div className="w-7 h-7 rounded-xl bg-indigo-600/20 text-indigo-400 group-hover:bg-indigo-600 group-hover:text-white flex items-center justify-center transition-all">
              <Plus className="w-4 h-4" />
            </div>
            <span className="text-xs font-semibold tracking-wide">New chat</span>
          </button>
        </div>

        {/* Previous Chats Label */}
        <div className="px-4 pt-2 pb-1.5 flex items-center justify-between text-[11px] font-bold text-slate-400 uppercase tracking-wider">
          <span>Recent</span>
          <span className="text-[10px] text-slate-500 font-mono font-normal">
            {conversations.length} {conversations.length === 1 ? 'chat' : 'chats'}
          </span>
        </div>

        {/* Previous Chats List (Sorted by Last Update Time) */}
        <div className="flex-1 overflow-y-auto px-2.5 space-y-1 scrollbar-thin">
          {conversations.length === 0 ? (
            <div className="text-center py-10 px-4 text-xs text-slate-500">
              No previous chats yet. Click <span className="text-indigo-400 font-medium">+ New chat</span> to begin!
            </div>
          ) : (
            conversations.map((conv) => {
              const isActive = conv._id === activeConversationId;
              const relativeTime = formatRelativeTime(conv.updatedAt || conv.createdAt);

              return (
                <div
                  key={conv._id}
                  onClick={() => loadConversation(conv._id)}
                  className={`group relative flex items-center justify-between p-3 rounded-xl cursor-pointer transition-all border ${
                    isActive
                      ? 'bg-slate-800/90 text-white border-slate-700 shadow-xs'
                      : 'bg-transparent text-slate-300 hover:bg-slate-800/50 hover:text-white border-transparent'
                  }`}
                >
                  <div className="flex items-center gap-2.5 truncate pr-2">
                    <MessageSquare
                      className={`w-3.5 h-3.5 shrink-0 ${
                        isActive ? 'text-indigo-400' : 'text-slate-500 group-hover:text-slate-400'
                      }`}
                    />
                    <div className="truncate text-left">
                      <p className="text-xs font-medium truncate leading-tight">
                        {conv.title || 'Untitled Chat'}
                      </p>
                      <span className="text-[10px] text-slate-500 mt-0.5 block">
                        {relativeTime} • {conv.messageCount || 0} msgs
                      </span>
                    </div>
                  </div>

                  {/* Delete conversation icon on hover */}
                  <button
                    onClick={(e) => handleDeleteConversation(e, conv._id)}
                    className="opacity-0 group-hover:opacity-100 p-1 text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 rounded-lg transition-all cursor-pointer shrink-0"
                    title="Delete chat session"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              );
            })
          )}
        </div>

        {/* Sidebar Footer: Course & User status */}
        <div className="p-3.5 border-t border-slate-800/60 bg-[#0a0f1d] flex items-center justify-between text-xs text-slate-400">
          <div className="flex items-center gap-2 truncate">
            <div className="w-6 h-6 rounded-full bg-gradient-to-tr from-indigo-500 to-purple-500 flex items-center justify-center text-white text-[11px] font-bold">
              {user?.name?.[0]?.toUpperCase() || 'U'}
            </div>
            <span className="truncate max-w-[150px] font-medium text-slate-300">
              {user?.name || 'Student'}
            </span>
          </div>

          <Link
            to={`/courses/${courseId}`}
            className="text-[11px] text-indigo-400 hover:underline shrink-0"
          >
            Course Page
          </Link>
        </div>
      </aside>

      {/* ============================================================ */}
      {/* MAJOR SECTION: CURRENT ONGOING CHAT (GEMINI STYLE)          */}
      {/* ============================================================ */}
      <main className="flex-1 flex flex-col h-full bg-[#080d1a] relative overflow-hidden">
        {/* Top Floating App Bar */}
        <header className="h-14 border-b border-slate-800/60 px-4 sm:px-6 flex items-center justify-between bg-[#080d1a]/80 backdrop-blur-md z-10 shrink-0">
          <div className="flex items-center gap-3">
            {!sidebarOpen && (
              <button
                onClick={() => setSidebarOpen(true)}
                className="p-2 text-slate-400 hover:text-white rounded-xl hover:bg-slate-800/80 transition-colors cursor-pointer"
                title="Open chat list"
              >
                <Menu className="w-4 h-4" />
              </button>
            )}

            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-indigo-600 via-purple-600 to-pink-500 text-white flex items-center justify-center shadow-md">
                <Sparkles className="w-4 h-4 animate-pulse" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="text-sm font-bold text-white tracking-tight">Buddy</h1>
                  <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
                    {course?.code} AI
                  </span>
                </div>
                <p className="text-[10px] text-slate-400">Grounded strictly in lecture recordings</p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleStartNewChat}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-indigo-300 bg-indigo-500/10 hover:bg-indigo-500/20 border border-indigo-500/30 rounded-xl transition-all cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">New Chat</span>
            </button>
          </div>
        </header>

        {/* Central Chat Feed */}
        <div className="flex-1 overflow-y-auto px-4 sm:px-8 py-6 scrollbar-thin">
          <div className="max-w-3xl mx-auto w-full flex flex-col justify-between min-h-full">
            {/* Condition 1: EMPTY / NEW CHAT GEMINI HERO GREETING */}
            {messages.length === 0 ? (
              <div className="flex-1 flex flex-col justify-center items-center py-12 text-center select-none animate-in fade-in duration-300">
                <div className="w-16 h-16 rounded-3xl bg-gradient-to-tr from-indigo-500 via-purple-500 to-pink-500 p-0.5 shadow-xl shadow-indigo-500/20 mb-6">
                  <div className="w-full h-full bg-[#0c1222] rounded-[22px] flex items-center justify-center text-white">
                    <Sparkles className="w-8 h-8 text-indigo-400" />
                  </div>
                </div>

                <h2 className="text-2xl sm:text-3xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-white via-slate-200 to-indigo-300 tracking-tight">
                  Hello, {user?.name?.split(' ')[0] || 'Student'}
                </h2>
                <p className="text-sm text-slate-400 mt-2 max-w-md leading-relaxed">
                  How can Buddy help you master <span className="text-indigo-300 font-semibold">{course?.code}</span> today?
                  Ask any question and I’ll cite the exact video moments from your professor’s lectures.
                </p>

                {/* Gemini-style 2x2 Suggestion Cards */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full mt-10 text-left">
                  {suggestionCards.map((card, idx) => (
                    <button
                      key={idx}
                      onClick={() => handleSendMessage(card.prompt)}
                      className="p-4 rounded-2xl bg-slate-850/60 hover:bg-slate-800/80 border border-slate-800 hover:border-indigo-500/40 shadow-sm hover:shadow-md transition-all text-left group cursor-pointer"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xl mb-1">{card.icon}</span>
                        <ChevronRight className="w-4 h-4 text-slate-600 group-hover:text-indigo-400 group-hover:translate-x-0.5 transition-all" />
                      </div>
                      <h3 className="text-xs font-semibold text-slate-200 group-hover:text-white mt-1">
                        {card.title}
                      </h3>
                      <p className="text-[11px] text-slate-400 line-clamp-2 mt-0.5">
                        {card.prompt}
                      </p>
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              /* Condition 2: ONGOING CHAT MESSAGE STREAM */
              <div className="space-y-6 pb-6 animate-in fade-in duration-200">
                {messages.map((msg, i) => (
                  <div
                    key={i}
                    className={`flex flex-col ${
                      msg.sender === 'student' ? 'items-end' : 'items-start'
                    }`}
                  >
                    {/* Message Bubble Container */}
                    <div className="flex items-start gap-3 max-w-[90%] sm:max-w-[85%]">
                      {/* Buddy Avatar */}
                      {msg.sender === 'assistant' && (
                        <div className="w-7 h-7 rounded-xl bg-gradient-to-tr from-indigo-600 to-purple-600 text-white flex items-center justify-center shrink-0 mt-0.5 shadow-sm">
                          <Sparkles className="w-3.5 h-3.5" />
                        </div>
                      )}

                      <div
                        className={`rounded-2xl px-5 py-3.5 leading-relaxed text-xs sm:text-[13px] whitespace-pre-wrap ${
                          msg.sender === 'student'
                            ? 'bg-indigo-600 text-white rounded-br-xs shadow-md'
                            : 'bg-slate-850/90 text-slate-100 rounded-bl-xs border border-slate-700/60 shadow-sm prose-invert'
                        }`}
                      >
                        {msg.text || (msg.isStreaming ? 'Thinking...' : '')}
                      </div>

                      {/* Student Avatar */}
                      {msg.sender === 'student' && (
                        <div className="w-7 h-7 rounded-xl bg-slate-800 border border-slate-700 text-slate-300 flex items-center justify-center shrink-0 mt-0.5 font-bold text-xs">
                          {user?.name?.[0]?.toUpperCase() || 'S'}
                        </div>
                      )}
                    </div>

                    {/* Interactive Video Timestamp Citations */}
                    {msg.citations && msg.citations.length > 0 && (
                      <div className="mt-2.5 ml-10 flex flex-wrap gap-2 max-w-[85%]">
                        {msg.citations.map((cite, cIdx) => (
                          <button
                            key={cIdx}
                            onClick={() =>
                              handleOpenCitationVideo(
                                cite.lectureId,
                                cite.startTime,
                                cite.chunkText,
                                cite.lectureTitle
                              )
                            }
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-medium rounded-xl bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-300 hover:text-white border border-indigo-500/30 shadow-xs transition-all cursor-pointer active:scale-95 group"
                            title={`Jump to video at ${formatSeconds(cite.startTime)}`}
                          >
                            <span className="w-4 h-4 rounded-full bg-indigo-600 text-white flex items-center justify-center group-hover:scale-110 transition-transform">
                              <Play className="w-2 h-2 fill-current ml-0.5" />
                            </span>
                            <span className="font-semibold truncate max-w-[160px]">
                              {cite.lectureTitle || 'Lecture'}
                            </span>
                            <span className="font-mono text-indigo-400 text-[10px]">
                              @{formatSeconds(cite.startTime)}
                            </span>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                ))}

                {/* Loading indicator while streaming */}
                {streaming && (
                  <div className="flex items-center gap-2 text-xs text-indigo-400 italic pl-10">
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Buddy is synthesizing grounded response from lecture transcripts...</span>
                  </div>
                )}

                <div ref={chatBottomRef} />
              </div>
            )}
          </div>
        </div>

        {/* ============================================================ */}
        {/* GEMINI-STYLE FLOATING BOTTOM CAPSULE INPUT                   */}
        {/* ============================================================ */}
        <div className="p-4 sm:p-6 pt-2 shrink-0 bg-gradient-to-t from-[#080d1a] via-[#080d1a] to-transparent">
          <div className="max-w-3xl mx-auto w-full">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSendMessage();
              }}
              className="relative flex items-center bg-[#131b2e] border border-slate-700/80 focus-within:border-indigo-500/80 focus-within:ring-2 focus-within:ring-indigo-500/20 rounded-3xl shadow-2xl p-2 transition-all"
            >
              <input
                ref={inputRef}
                type="text"
                disabled={streaming}
                placeholder={`Ask Buddy anything about ${course?.code || 'this course'} lectures...`}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                className="w-full text-xs sm:text-sm py-2 px-4 bg-transparent text-white placeholder:text-slate-500 focus:outline-none disabled:opacity-50"
              />

              <button
                type="submit"
                disabled={!query.trim() || streaming}
                className="w-9 h-9 rounded-2xl bg-indigo-600 hover:bg-indigo-500 text-white flex items-center justify-center shrink-0 disabled:opacity-30 disabled:hover:bg-indigo-600 transition-all shadow-md active:scale-95 cursor-pointer ml-1"
                title="Send to Buddy"
              >
                <Send className="w-4 h-4" />
              </button>
            </form>

            {/* Bottom Disclaimer */}
            <p className="text-[10px] text-slate-500 text-center mt-2">
              Buddy grounds answers strictly in {course?.code} professor recordings. Click video badges to jump to exact moments.
            </p>
          </div>
        </div>
      </main>

      {/* ============================================================ */}
      {/* SYNCHRONIZED VIDEO CITATION MODAL                            */}
      {/* ============================================================ */}
      {activeCitationVideo && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4 animate-in fade-in duration-150">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl overflow-hidden max-w-3xl w-full shadow-2xl flex flex-col">
            {/* Modal Header */}
            <div className="p-4 border-b border-slate-800 flex items-center justify-between bg-slate-950">
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-xl bg-indigo-600/20 text-indigo-400 flex items-center justify-center">
                  <Play className="w-3.5 h-3.5 fill-current" />
                </div>
                <div>
                  <h3 className="text-xs font-bold text-white">
                    {activeCitationVideo.lectureTitle}
                  </h3>
                  <span className="text-[10px] text-indigo-400 font-mono">
                    Jumped to {formatSeconds(activeCitationVideo.startTime)}
                  </span>
                </div>
              </div>

              <button
                onClick={() => setActiveCitationVideo(null)}
                className="p-1.5 text-slate-400 hover:text-white rounded-xl hover:bg-slate-800 transition-colors cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Video Player */}
            <div className="p-4 bg-black flex justify-center">
              <div className="w-full max-w-2xl aspect-video">
                <VideoPlayer
                  ref={modalVideoRef}
                  selectedLecture={activeCitationVideo.lecture}
                />
              </div>
            </div>

            {/* Transcript Excerpt Card */}
            {activeCitationVideo.chunkText && (
              <div className="p-4 bg-slate-950/70 border-t border-slate-800/80 text-xs text-slate-300">
                <span className="font-semibold text-indigo-400 block mb-1">
                  Cited Lecture Transcript:
                </span>
                <p className="italic text-slate-400 leading-relaxed text-[11px]">
                  "{activeCitationVideo.chunkText}"
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
