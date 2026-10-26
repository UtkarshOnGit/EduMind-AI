import axios from 'axios';
import Conversation from '../models/Conversation.js';

/**
 * @desc    Stream course AI chatbot response via SSE & save conversation history to specific chat session
 * @route   POST /api/v1/courses/:courseId/chat
 * @access  Private (Student enrolled or Professor owner)
 */
export const streamCourseChat = async (req, res) => {
  try {
    const { courseId } = req.params;
    const { query, conversationId } = req.body;

    if (!query || !query.trim()) {
      return res.status(400).json({ success: false, message: 'Query string is required' });
    }

    const userId = req.user._id;

    // 1. Find existing conversation by conversationId or create a new dedicated chat session
    let conversation = null;
    if (conversationId) {
      conversation = await Conversation.findOne({
        _id: conversationId,
        studentId: userId,
        courseId
      });
    }

    // If no valid conversation found or no conversationId supplied, start a new chat session
    if (!conversation) {
      const cleanTitle = query.trim().slice(0, 45) + (query.trim().length > 45 ? '...' : '');
      conversation = await Conversation.create({
        studentId: userId,
        courseId,
        title: cleanTitle,
        messages: []
      });
    }

    // 2. Format short-term conversational memory for LangGraph workflow
    const history = (conversation.messages || []).slice(-8).map((msg) => ({
      sender: msg.sender,
      text: msg.text
    }));

    // 3. Dispatch to FastAPI AI Service SSE endpoint
    const aiServiceUrl = process.env.AI_SERVICE_URL || 'http://localhost:8000';
    const payload = {
      course_id: courseId,
      student_id: userId.toString(),
      conversation_id: conversation._id.toString(),
      query: query.trim(),
      history
    };

    let aiStreamResponse;
    try {
      aiStreamResponse = await axios.post(`${aiServiceUrl}/api/v1/chat/query`, payload, {
        responseType: 'stream',
        headers: { 'Content-Type': 'application/json' },
        timeout: 30000
      });
    } catch (aiErr) {
      console.error('[AI Service Connection Error]:', aiErr.message);
      return res.status(502).json({
        success: false,
        message: `Unable to connect to AI Service at ${aiServiceUrl}: ${aiErr.message}`
      });
    }

    // 4. Configure client SSE headers
    res.setHeader('Content-Type', 'text/event-stream');
    res.setHeader('Cache-Control', 'no-cache, no-transform');
    res.setHeader('Connection', 'keep-alive');
    res.setHeader('X-Accel-Buffering', 'no');
    if (res.flushHeaders) res.flushHeaders();

    // Send conversation metadata header event so the client associates the message with this session
    res.write(
      `data: ${JSON.stringify({
        conversationId: conversation._id.toString(),
        title: conversation.title
      })}\n\n`
    );

    let assistantFullText = '';
    let citations = [];

    // Proxy stream chunks to the client
    aiStreamResponse.data.on('data', (chunk) => {
      const chunkStr = chunk.toString();
      res.write(chunkStr);

      // Accumulate tokens and citations for MongoDB persistence
      const lines = chunkStr.split('\n');
      for (const line of lines) {
        if (line.startsWith('data: ') && !line.includes('[DONE]')) {
          try {
            const data = JSON.parse(line.replace('data: ', '').trim());
            if (data.token) {
              assistantFullText += data.token;
            }
            if (data.citations && Array.isArray(data.citations)) {
              citations = data.citations.map((c) => ({
                lectureId: c.lecture_id || null,
                lectureTitle: c.lecture_title || 'Course Lecture',
                startTime: c.start_time || 0,
                endTime: c.end_time || 0,
                chunkText: c.chunk_text || ''
              }));
            }
          } catch (e) {
            // Ignore non-json chunk lines
          }
        }
      }
    });

    aiStreamResponse.data.on('end', async () => {
      res.end();

      // Persist the student question and assistant response into this conversation's state
      try {
        conversation.messages.push({
          sender: 'student',
          text: query.trim(),
          createdAt: new Date()
        });
        conversation.messages.push({
          sender: 'assistant',
          text: assistantFullText.trim(),
          citations,
          createdAt: new Date()
        });
        await conversation.save();
      } catch (saveErr) {
        console.error('[Save Conversation Error]:', saveErr.message);
      }
    });

    aiStreamResponse.data.on('error', (err) => {
      console.error('[AI Stream Error]:', err.message);
      res.write(`data: ${JSON.stringify({ error: err.message })}\n\n`);
      res.end();
    });

    req.on('close', () => {
      if (aiStreamResponse.data) {
        aiStreamResponse.data.destroy();
      }
    });
  } catch (error) {
    console.error('[Stream Course Chat Error]:', error);
    if (!res.headersSent) {
      res.status(500).json({ success: false, message: error.message });
    }
  }
};

/**
 * @desc    List all conversation sessions for the current student in a course
 * @route   GET /api/v1/courses/:courseId/conversations
 * @access  Private (Student enrolled or Professor owner)
 */
export const getCourseConversations = async (req, res) => {
  try {
    const { courseId } = req.params;
    const userId = req.user._id;

    const conversations = await Conversation.find({ studentId: userId, courseId })
      .sort({ updatedAt: -1 })
      .select('_id title createdAt updatedAt messages');

    const formatted = conversations.map((conv) => ({
      _id: conv._id,
      title: conv.title,
      createdAt: conv.createdAt,
      updatedAt: conv.updatedAt,
      messageCount: conv.messages ? conv.messages.length : 0,
      preview: conv.messages && conv.messages.length > 0 ? conv.messages[conv.messages.length - 1].text : ''
    }));

    res.json({
      success: true,
      count: formatted.length,
      data: formatted
    });
  } catch (error) {
    console.error('[Get Course Conversations Error]:', error);
    res.status(500).json({ success: false, message: error.message });
  }
};

/**
 * @desc    Get specific conversation session by ID with its messages
 * @route   GET /api/v1/courses/:courseId/conversations/:conversationId
 * @access  Private
 */
export const getConversationById = async (req, res) => {
  try {
    const { courseId, conversationId } = req.params;
    const userId = req.user._id;

    const conversation = await Conversation.findOne({
      _id: conversationId,
      studentId: userId,
      courseId
    });

    if (!conversation) {
      return res.status(404).json({ success: false, message: 'Conversation session not found' });
    }

    res.json({
      success: true,
      data: conversation
    });
  } catch (error) {
    console.error('[Get Conversation Details Error]:', error);
    res.status(500).json({ success: false, message: error.message });
  }
};

/**
 * @desc    Create a new empty conversation session
 * @route   POST /api/v1/courses/:courseId/conversations
 * @access  Private
 */
export const createConversation = async (req, res) => {
  try {
    const { courseId } = req.params;
    const { title } = req.body;
    const userId = req.user._id;

    const conversation = await Conversation.create({
      studentId: userId,
      courseId,
      title: title && title.trim() ? title.trim() : 'New Chat',
      messages: []
    });

    res.status(201).json({
      success: true,
      data: conversation
    });
  } catch (error) {
    console.error('[Create Conversation Error]:', error);
    res.status(500).json({ success: false, message: error.message });
  }
};

/**
 * @desc    Delete a specific conversation session
 * @route   DELETE /api/v1/courses/:courseId/conversations/:conversationId
 * @access  Private
 */
export const deleteConversation = async (req, res) => {
  try {
    const { courseId, conversationId } = req.params;
    const userId = req.user._id;

    const deleted = await Conversation.findOneAndDelete({
      _id: conversationId,
      studentId: userId,
      courseId
    });

    if (!deleted) {
      return res.status(404).json({ success: false, message: 'Conversation not found' });
    }

    res.json({
      success: true,
      message: 'Conversation deleted successfully'
    });
  } catch (error) {
    console.error('[Delete Conversation Error]:', error);
    res.status(500).json({ success: false, message: error.message });
  }
};

// Backwards compatibility helpers
export const getCourseConversation = getCourseConversations;
export const clearCourseConversation = async (req, res) => {
  try {
    const { courseId } = req.params;
    const userId = req.user._id;
    await Conversation.deleteMany({ studentId: userId, courseId });
    res.json({ success: true, message: 'All conversations cleared' });
  } catch (err) {
    res.status(500).json({ success: false, message: err.message });
  }
};

