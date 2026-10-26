import Course from '../models/Course.js';

/**
 * @desc    Create a new course
 * @route   POST /api/v1/courses
 * @access  Private (Professor only)
 */
export const createCourse = async (req, res) => {
  try {
    const { code, title, description } = req.body;

    if (!code || !title) {
      return res.status(400).json({ success: false, message: 'Please provide course code and title' });
    }

    const existingCourse = await Course.findOne({ code: code.toUpperCase().trim() });
    if (existingCourse) {
      return res.status(400).json({ success: false, message: `Course with code ${code} already exists` });
    }

    const course = await Course.create({
      code: code.toUpperCase().trim(),
      title,
      description: description || '',
      professor: req.user._id,
      enrolledStudents: []
    });

    res.status(201).json({
      success: true,
      data: course
    });
  } catch (error) {
    console.error('[Create Course Error]:', error);
    res.status(500).json({ success: false, message: error.message });
  }
};

/**
 * @desc    Get courses for current user (created courses for professors, enrolled courses for students)
 * @route   GET /api/v1/courses/my
 * @access  Private
 */
export const getMyCourses = async (req, res) => {
  try {
    let courses;
    if (req.user.role === 'professor') {
      courses = await Course.find({ professor: req.user._id })
        .populate('professor', 'name email')
        .sort({ createdAt: -1 });
    } else {
      courses = await Course.find({ enrolledStudents: req.user._id })
        .populate('professor', 'name email')
        .sort({ createdAt: -1 });
    }

    res.json({
      success: true,
      count: courses.length,
      data: courses
    });
  } catch (error) {
    console.error('[Get My Courses Error]:', error);
    res.status(500).json({ success: false, message: error.message });
  }
};

/**
 * @desc    Get all available courses (Catalog)
 * @route   GET /api/v1/courses/catalog
 * @access  Private
 */
export const getCatalogCourses = async (req, res) => {
  try {
    const courses = await Course.find()
      .populate('professor', 'name email')
      .select('-__v')
      .sort({ createdAt: -1 });

    res.json({
      success: true,
      count: courses.length,
      data: courses
    });
  } catch (error) {
    console.error('[Get Catalog Courses Error]:', error);
    res.status(500).json({ success: false, message: error.message });
  }
};

/**
 * @desc    Get single course by ID
 * @route   GET /api/v1/courses/:courseId
 * @access  Private (Course Access: Professor owner or enrolled student)
 */
export const getCourseById = async (req, res) => {
  try {
    const course = await Course.findById(req.params.courseId)
      .populate('professor', 'name email')
      .populate('enrolledStudents', 'name email');

    if (!course) {
      return res.status(404).json({ success: false, message: 'Course not found' });
    }

    res.json({
      success: true,
      data: course
    });
  } catch (error) {
    console.error('[Get Course By ID Error]:', error);
    res.status(500).json({ success: false, message: error.message });
  }
};

/**
 * @desc    Enroll student in a course
 * @route   POST /api/v1/courses/:courseId/enroll
 * @access  Private (Student only)
 */
export const enrollInCourse = async (req, res) => {
  try {
    const course = await Course.findById(req.params.courseId);
    if (!course) {
      return res.status(404).json({ success: false, message: 'Course not found' });
    }

    const alreadyEnrolled = course.enrolledStudents.some(
      (id) => id.toString() === req.user._id.toString()
    );

    if (alreadyEnrolled) {
      return res.status(400).json({ success: false, message: 'Already enrolled in this course' });
    }

    course.enrolledStudents.push(req.user._id);
    await course.save();

    res.json({
      success: true,
      message: `Successfully enrolled in ${course.code} - ${course.title}`,
      data: course
    });
  } catch (error) {
    console.error('[Enroll Course Error]:', error);
    res.status(500).json({ success: false, message: error.message });
  }
};
