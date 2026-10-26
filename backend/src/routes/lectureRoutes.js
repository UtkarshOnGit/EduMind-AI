import express from 'express';
import {
  getSignedUploadUrl,
  createLecture,
  getLectureById,
  updateLectureStatus
} from '../controllers/lectureController.js';
import { protect } from '../middleware/auth.js';
import { requireRole } from '../middleware/rbac.js';

const router = express.Router();

// Direct Cloudinary upload signature generation
router.get('/signed-upload', protect, requireRole('professor'), getSignedUploadUrl);

// Create lecture metadata (Professor only)
router.post('/', protect, requireRole('professor'), createLecture);

// Get single lecture by ID (Protected)
router.get('/:lectureId', protect, getLectureById);

// Webhook/Internal callback for FastAPI AI Service to report status & transcript blocks
router.patch('/:lectureId/status', updateLectureStatus);

export default router;
