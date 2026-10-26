import React, { useState } from 'react';
import axios from 'axios';
import api from '../services/api';
import { Upload, X, Film, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';

export default function UploadLectureModal({ isOpen, onClose, courseId, onLectureUploaded }) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [stage, setStage] = useState(''); // 'signing' | 'uploading' | 'registering'
  const [error, setError] = useState('');

  if (!isOpen) return null;

  const handleFileChange = (e) => {
    const selected = e.target.files[0];
    if (selected) {
      if (!selected.type.startsWith('video/')) {
        setError('Please select a valid video file (.mp4, .mov, .webm, etc.)');
        return;
      }
      setFile(selected);
      setError('');
      if (!title) {
        // Prepopulate title with filename minus extension
        const cleanName = selected.name.replace(/\.[^/.]+$/, '').replace(/[-_]/g, ' ');
        setTitle(cleanName.charAt(0).toUpperCase() + cleanName.slice(1));
      }
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file || !title.trim()) {
      setError('Lecture title and video file are required.');
      return;
    }

    try {
      setUploading(true);
      setError('');
      setProgress(5);
      setStage('Requesting secure upload authorization...');

      // Step 1: Request signed upload params from Node.js backend
      const signRes = await api.get('/lectures/signed-upload');
      const { timestamp, folder, signature, apiKey, cloudName } = signRes.data.data;

      if (!cloudName || cloudName === 'your_cloud_name') {
        throw new Error(
          'Cloudinary is not configured on the backend yet. Please set CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET in backend/.env'
        );
      }

      // Step 2: Upload video directly to Cloudinary bypassing Node server
      setStage('Uploading video directly to Cloudinary...');
      const formData = new FormData();
      formData.append('file', file);
      formData.append('api_key', apiKey);
      formData.append('timestamp', timestamp);
      formData.append('signature', signature);
      formData.append('folder', folder);

      const cloudinaryUploadUrl = `https://api.cloudinary.com/v1_1/${cloudName}/video/upload`;
      const cloudRes = await axios.post(cloudinaryUploadUrl, formData, {
        onUploadProgress: (progressEvent) => {
          if (progressEvent.total) {
            const pct = Math.round((progressEvent.loaded * 85) / progressEvent.total);
            setProgress(Math.max(10, pct));
          }
        }
      });

      const { secure_url, public_id, duration } = cloudRes.data;

      // Step 3: Register lecture metadata in Node backend and trigger FastAPI AI ingestion
      setStage('Registering lecture & starting AI processing...');
      setProgress(95);

      await api.post('/lectures', {
        courseId,
        title: title.trim(),
        description: description.trim(),
        cloudinaryUrl: secure_url,
        cloudinaryPublicId: public_id,
        duration: Math.round(duration || 0)
      });

      setProgress(100);
      setStage('Upload complete!');

      setTimeout(() => {
        setUploading(false);
        onLectureUploaded();
        onClose();
      }, 800);
    } catch (err) {
      console.error('Upload Error:', err);
      const msg =
        err.response?.data?.error?.message ||
        err.response?.data?.message ||
        err.message ||
        'Failed to upload lecture video.';
      setError(msg);
      setUploading(false);
      setProgress(0);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in duration-200">
      <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-100 relative text-slate-900">
        <button
          onClick={onClose}
          disabled={uploading}
          className="absolute top-4 right-4 text-slate-400 hover:text-slate-600 p-1.5 rounded-lg hover:bg-slate-100 transition-colors disabled:opacity-40"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-3 mb-5">
          <div className="w-10 h-10 rounded-xl bg-indigo-50 border border-indigo-100 text-indigo-600 flex items-center justify-center">
            <Upload className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-slate-900">Upload Course Lecture</h2>
            <p className="text-xs text-slate-500">Direct cloud ingestion with automated AI transcription</p>
          </div>
        </div>

        {error && (
          <div className="mb-4 p-3 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs flex items-start gap-2">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Lecture Title <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              required
              disabled={uploading}
              placeholder="e.g., Lecture 4: CAP Theorem & Consistency"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full text-xs px-3.5 py-2.5 rounded-xl border border-slate-300 bg-white text-slate-900 font-medium placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 transition-all shadow-xs"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Description <span className="text-slate-400 font-normal">(Optional)</span>
            </label>
            <textarea
              rows={2}
              disabled={uploading}
              placeholder="Brief summary of concepts covered..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full text-xs px-3.5 py-2 rounded-xl border border-slate-300 bg-white text-slate-900 font-medium placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 transition-all resize-none shadow-xs"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Video File <span className="text-red-500">*</span>
            </label>
            <div className="border-2 border-dashed border-slate-200 hover:border-indigo-400 rounded-xl p-4 text-center cursor-pointer transition-colors bg-slate-50/50">
              <input
                type="file"
                accept="video/*"
                disabled={uploading}
                onChange={handleFileChange}
                className="hidden"
                id="lecture-video-input"
              />
              <label htmlFor="lecture-video-input" className="cursor-pointer block">
                <Film className="w-8 h-8 text-indigo-500 mx-auto mb-2" />
                {file ? (
                  <div className="text-xs">
                    <span className="font-semibold text-slate-800">{file.name}</span>
                    <span className="text-slate-400 block text-[11px] mt-0.5">
                      {(file.size / (1024 * 1024)).toFixed(1)} MB
                    </span>
                  </div>
                ) : (
                  <div>
                    <span className="text-xs font-medium text-indigo-600 hover:underline">
                      Click to choose video file
                    </span>
                    <span className="block text-[10px] text-slate-400 mt-1">MP4, MOV, WebM (up to 500MB)</span>
                  </div>
                )}
              </label>
            </div>
          </div>

          {/* Upload Progress Bar */}
          {uploading && (
            <div className="pt-2">
              <div className="flex items-center justify-between text-xs mb-1.5">
                <span className="font-medium text-slate-700 flex items-center gap-1.5">
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-indigo-600" />
                  {stage}
                </span>
                <span className="font-bold text-indigo-600">{progress}%</span>
              </div>
              <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                <div
                  className="bg-indigo-600 h-full rounded-full transition-all duration-300"
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>
          )}

          <div className="flex justify-end gap-2.5 pt-3 border-t border-slate-100">
            <button
              type="button"
              onClick={onClose}
              disabled={uploading}
              className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 hover:bg-slate-100 transition-colors disabled:opacity-40"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={uploading || !file || !title.trim()}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 transition-all shadow-sm disabled:opacity-40 disabled:pointer-events-none"
            >
              {uploading ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Processing...</span>
                </>
              ) : (
                <>
                  <Upload className="w-3.5 h-3.5" />
                  <span>Start Upload</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
