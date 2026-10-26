import axios from 'axios';
import Lecture from '../models/Lecture.js';
import TranscriptBlock from '../models/TranscriptBlock.js';
import { generateSignedUploadParams } from '../config/cloudinary.js';

/**
 * @desc    Generate Cloudinary signed upload credentials
 * @route   GET /api/v1/lectures/signed-upload
 * @access  Private (Professor only)
 */
export const getSignedUploadUrl = async (req, res) => {
  try {
    const signedParams = generateSignedUploadParams();
    res.json({
      success: true,
      data: signedParams
    });
  } catch (error) {
    console.error('[Signed Upload Error]:', error);
    res.status(500).json({ success: false, message: 'Failed to generate upload signature' });
  }
};

/**
 * @desc    Save uploaded lecture metadata & trigger FastAPI ingestion
 * @route   POST /api/v1/lectures
 * @access  Private (Professor only)
 */
export const createLecture = async (req, res) => {
  try {
    const { courseId, title, description, cloudinaryUrl, cloudinaryPublicId, duration } = req.body;

    if (!courseId || !title || !cloudinaryUrl || !cloudinaryPublicId) {
      return res.status(400).json({
        success: false,
        message: 'courseId, title, cloudinaryUrl, and cloudinaryPublicId are required'
      });
    }

    // Create lecture record in MongoDB
    const lecture = await Lecture.create({
      courseId,
      title,
      description: description || '',
      cloudinaryUrl,
      cloudinaryPublicId,
      duration: duration || 0,
      status: 'uploaded'
    });

    // Asynchronously notify FastAPI AI Service to start audio extraction & indexing
    const aiServiceUrl = process.env.AI_SERVICE_URL || 'http://localhost:8000';
    axios
      .post(`${aiServiceUrl}/api/v1/ingest/lecture`, {
        lecture_id: lecture._id.toString(),
        course_id: courseId.toString(),
        title: lecture.title,
        cloudinary_url: cloudinaryUrl
      })
      .catch((err) => {
        console.warn(`[AI Service Trigger Warning]: Unable to contact AI service at ${aiServiceUrl} - ${err.message}`);
      });

    res.status(201).json({
      success: true,
      message: 'Lecture uploaded and scheduled for processing',
      data: lecture
    });
  } catch (error) {
    console.error('[Create Lecture Error]:', error);
    res.status(500).json({ success: false, message: error.message });
  }
};

/**
 * @desc    Get all lectures for a specific course
 * @route   GET /api/v1/courses/:courseId/lectures
 * @access  Private (Course Access: Professor owner or enrolled student)
 */
export const getLecturesByCourse = async (req, res) => {
  try {
    const { courseId } = req.params;
    const lectures = await Lecture.find({ courseId }).sort({ createdAt: 1 });

    res.json({
      success: true,
      count: lectures.length,
      data: lectures
    });
  } catch (error) {
    console.error('[Get Lectures Error]:', error);
    res.status(500).json({ success: false, message: error.message });
  }
};

/**
 * @desc    Get single lecture by ID with transcript blocks
 * @route   GET /api/v1/lectures/:lectureId
 * @access  Private
 */
export const getLectureById = async (req, res) => {
  try {
    const lecture = await Lecture.findById(req.params.lectureId);
    if (!lecture) {
      return res.status(404).json({ success: false, message: 'Lecture not found' });
    }

    const transcriptBlocks = await TranscriptBlock.find({ lectureId: lecture._id }).sort({ blockIndex: 1 });

    res.json({
      success: true,
      data: {
        ...lecture.toObject(),
        transcriptBlocks
      }
    });
  } catch (error) {
    console.error('[Get Lecture Details Error]:', error);
    res.status(500).json({ success: false, message: error.message });
  }
};

/**
 * @desc    Webhook/Callback endpoint for FastAPI AI Service to report status and save transcript blocks
 * @route   PATCH /api/v1/lectures/:lectureId/status
 * @access  Internal/Protected (Can be protected by internal secret)
 */
export const updateLectureStatus = async (req, res) => {
  try {
    const { lectureId } = req.params;
    const { status, processingError, transcriptBlocks } = req.body;

    const lecture = await Lecture.findById(lectureId);
    if (!lecture) {
      return res.status(404).json({ success: false, message: 'Lecture not found' });
    }

    if (status) lecture.status = status;
    if (processingError !== undefined) lecture.processingError = processingError;
    await lecture.save();

    // Optionally save transcript blocks if sent in batch
    if (Array.isArray(transcriptBlocks) && transcriptBlocks.length > 0) {
      // Upsert transcript blocks
      for (const block of transcriptBlocks) {
        await TranscriptBlock.findOneAndUpdate(
          { lectureId: lecture._id, blockIndex: block.blockIndex },
          {
            courseId: lecture.courseId,
            lectureId: lecture._id,
            blockIndex: block.blockIndex,
            startTime: block.startTime,
            endTime: block.endTime,
            text: block.text
          },
          { upsert: true, new: true }
        );
      }
    }

    res.json({
      success: true,
      message: 'Lecture status updated successfully',
      data: lecture
    });
  } catch (error) {
    console.error('[Update Lecture Status Error]:', error);
    res.status(500).json({ success: false, message: error.message });
  }
};
