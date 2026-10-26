import express from 'express';
import {
  createCourse,
  getMyCourses,
  getCatalogCourses,
  getCourseById,
  enrollInCourse
} from '../controllers/courseController.js';
import { getLecturesByCourse } from '../controllers/lectureController.js';
import {
  streamCourseChat,
  getCourseConversation,
  clearCourseConversation,
  getCourseConversations,
  getConversationById,
  createConversation,
  deleteConversation
} from '../controllers/chatController.js';
import { protect } from '../middleware/auth.js';
import { requireRole, verifyCourseAccess } from '../middleware/rbac.js';

const router = express.Router();

router.use(protect); // All course routes require authentication

router.get('/my', getMyCourses);
router.get('/catalog', getCatalogCourses);
router.post('/', requireRole('professor'), createCourse);
router.get('/:courseId', verifyCourseAccess, getCourseById);
router.post('/:courseId/enroll', requireRole('student'), enrollInCourse);
router.get('/:courseId/lectures', verifyCourseAccess, getLecturesByCourse);

// Course-Grounded AI Chat & Multi-Session Conversations
router.post('/:courseId/chat', verifyCourseAccess, streamCourseChat);
router.get('/:courseId/conversations', verifyCourseAccess, getCourseConversations);
router.post('/:courseId/conversations', verifyCourseAccess, createConversation);
router.get('/:courseId/conversations/:conversationId', verifyCourseAccess, getConversationById);
router.delete('/:courseId/conversations/:conversationId', verifyCourseAccess, deleteConversation);

// Legacy single-conversation endpoints
router.get('/:courseId/conversation', verifyCourseAccess, getCourseConversation);
router.delete('/:courseId/conversation', verifyCourseAccess, clearCourseConversation);

export default router;
