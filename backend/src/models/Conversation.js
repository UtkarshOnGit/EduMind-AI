import mongoose from 'mongoose';

const messageSchema = new mongoose.Schema({
  sender: {
    type: String,
    enum: ['student', 'assistant'],
    required: true
  },
  text: {
    type: String,
    required: true
  },
  citations: [
    {
      lectureId: { type: mongoose.Schema.Types.ObjectId, ref: 'Lecture' },
      lectureTitle: String,
      startTime: Number,
      endTime: Number,
      chunkText: String
    }
  ],
  createdAt: {
    type: Date,
    default: Date.now
  }
});

const conversationSchema = new mongoose.Schema(
  {
    studentId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'User',
      required: true,
      index: true
    },
    courseId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'Course',
      required: true,
      index: true
    },
    title: {
      type: String,
      default: 'New Conversation'
    },
    messages: [messageSchema]
  },
  { timestamps: true }
);

conversationSchema.index({ studentId: 1, courseId: 1 });

const Conversation = mongoose.model('Conversation', conversationSchema);
export default Conversation;
