import dotenv from 'dotenv';
dotenv.config();

import app from './app.js';
import { connectDB } from './config/db.js';
import { configureCloudinary } from './config/cloudinary.js';

// Connect to MongoDB
connectDB();

// Initialize Cloudinary SDK
configureCloudinary();

const PORT = process.env.PORT || 5001;

app.listen(PORT, () => {
  console.log(`[Edumind Backend] Server running on port ${PORT} in ${process.env.NODE_ENV || 'development'} mode`);
});
