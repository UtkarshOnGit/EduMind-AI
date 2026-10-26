import Course from '../models/Course.js';

/**
 * Restrict endpoint access to specified roles
 * @param  {...string} roles - e.g. 'professor', 'student'
 */
export const requireRole = (...roles) => {
  return (req, res, next) => {
    if (!req.user || !roles.includes(req.user.role)) {
      return res.status(403).json({
        success: false,
        message: `Forbidden: User role '${req.user?.role}' is not authorized to perform this action`
      });
    }
    next();
  };
};

/**
 * Verify that the user has permission to access the specified course:
 * - Professors must own the course
 * - Students must be enrolled in the course
 */
export const verifyCourseAccess = async (req, res, next) => {
  try {
    const courseId = req.params.courseId || req.body.courseId;
    if (!courseId) {
      return res.status(400).json({ success: false, message: 'Course ID is required' });
    }

    const course = await Course.findById(courseId);
    if (!course) {
      return res.status(404).json({ success: false, message: 'Course not found' });
    }

    // Attach course to req for downstream use
    req.course = course;

    // Professors can access only if they are the course creator
    if (req.user.role === 'professor') {
      if (course.professor.toString() !== req.user._id.toString()) {
        return res.status(403).json({
          success: false,
          message: 'Access denied: You do not own this course'
        });
      }
      return next();
    }

    // Students can access only if they are enrolled
    if (req.user.role === 'student') {
      const isEnrolled = course.enrolledStudents.some(
        (id) => id.toString() === req.user._id.toString()
      );
      if (!isEnrolled) {
        return res.status(403).json({
          success: false,
          message: 'Access denied: You are not enrolled in this course'
        });
      }
      return next();
    }

    return res.status(403).json({ success: false, message: 'Unauthorized role' });
  } catch (error) {
    console.error('[Verify Course Access Error]:', error.message);
    return res.status(500).json({ success: false, message: 'Server error verifying course access' });
  }
};
