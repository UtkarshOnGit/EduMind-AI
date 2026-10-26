import mongoose from 'mongoose';

const lectureSchema = new mongoose.Schema(
  {
    courseId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'Course',
      required: true,
      index: true
    },
    title: {
      type: String,
      required: [true, 'Lecture title is required'],
      trim: true
    },
    description: {
      type: String,
      default: ''
    },
    cloudinaryUrl: {
      type: String,
      required: true
    },
    cloudinaryPublicId: {
      type: String,
      required: true
    },
    duration: {
      type: Number,
      default: 0
    },
    status: {
      type: String,
      enum: ['uploaded', 'processing', 'processed', 'failed'],
      default: 'uploaded',
      index: true
    },
    processingError: {
      type: String,
      default: null
    }
  },
  { timestamps: true }
);

const Lecture = mongoose.model('Lecture', lectureSchema);
export default Lecture;
