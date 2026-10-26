import mongoose from 'mongoose';

const transcriptBlockSchema = new mongoose.Schema(
  {
    lectureId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'Lecture',
      required: true,
      index: true
    },
    courseId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'Course',
      required: true,
      index: true
    },
    blockIndex: {
      type: Number,
      required: true
    },
    startTime: {
      type: Number, // in seconds
      required: true
    },
    endTime: {
      type: Number, // in seconds
      required: true
    },
    text: {
      type: String,
      required: true
    }
  },
  { timestamps: true }
);

// Compound index for querying a lecture's blocks in order
transcriptBlockSchema.index({ lectureId: 1, blockIndex: 1 });

const TranscriptBlock = mongoose.model('TranscriptBlock', transcriptBlockSchema);
export default TranscriptBlock;
