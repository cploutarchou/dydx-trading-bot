/**
 * Profile Settings Component
 * Allows users to manage their profile information and upload avatars
 */

import { Camera, Check, Upload, X } from 'lucide-react';
import React, { useEffect, useRef, useState } from 'react';
import apiClient from '../api';
import { useAuthStore } from '../store/auth';

interface ProfileSettingsProps {
  onSave?: (profileData: ProfileUpdateData) => void;
}

export interface ProfileUpdateData {
  full_name?: string | null;
  email: string;
  avatar?: string; // Base64 encoded image
}

export const ProfileSettings: React.FC<ProfileSettingsProps> = () => {
  const { user } = useAuthStore();
  const [fullName, setFullName] = useState(user?.full_name || '');
  const [email, setEmail] = useState(user?.email || '');
  const [avatar, setAvatar] = useState<string | null>(user?.avatar || null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Load fresh user data on component mount
  useEffect(() => {
    const loadUserData = async () => {
      try {
        const response = await apiClient.getCurrentUser();
        const userData = response.data || response;
        console.log('✅ ProfileSettings: Loaded fresh user data:', userData);
        
        // Update auth store with fresh data
        useAuthStore.setState({ user: userData });
      } catch (error) {
        console.error('❌ ProfileSettings: Failed to load user data:', error);
      }
    };
    loadUserData();
  }, []);

  const handleAvatarClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate file type
    if (!file.type.startsWith('image/')) {
      setMessage({ type: 'error', text: 'Please select an image file' });
      return;
    }

    // Validate file size (max 5MB)
    if (file.size > 5 * 1024 * 1024) {
      setMessage({ type: 'error', text: 'Image must be less than 5MB' });
      return;
    }

    // Convert to base64
    const reader = new FileReader();
    reader.onload = (event) => {
      const base64 = event.target?.result as string;
      setAvatar(base64);
      setMessage({ type: 'success', text: 'Avatar updated' });
    };
    reader.onerror = () => {
      setMessage({ type: 'error', text: 'Failed to read file' });
    };
    reader.readAsDataURL(file);
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      setMessage(null);

      const profileData: ProfileUpdateData = {
        full_name: fullName || null,
        email: email,
        avatar: avatar || undefined,
      };

      // Call API to save profile
      const response = await apiClient.updateProfile(profileData);
      
      if (response.success) {
        // Update auth store with new user data
        const { user: updatedUser } = response.data;
        useAuthStore.setState({ user: updatedUser });
        
        setMessage({ type: 'success', text: 'Profile saved successfully' });
      } else {
        setMessage({
          type: 'error',
          text: response.message || 'Failed to save profile',
        });
      }
    } catch (error: any) {
      const errorMessage = error.response?.data?.detail || error.message || 'Failed to save profile';
      setMessage({
        type: 'error',
        text: errorMessage,
      });
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    setFullName(user?.full_name || '');
    setEmail(user?.email || '');
    setAvatar(user?.avatar || null);
    setMessage(null);
  };

  return (
    <div className="bg-slate-800 rounded-lg shadow p-6 border border-slate-700">
      {/* Message Display */}
      {message && (
        <div
          className={`mb-6 px-4 py-3 rounded border ${
            message.type === 'success'
              ? 'bg-green-900 border-green-700 text-green-100'
              : 'bg-red-900 border-red-700 text-red-100'
          }`}
        >
          {message.text}
        </div>
      )}

      {/* Section Header */}
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-white">Profile Settings</h2>
        <p className="text-gray-400 mt-1">Manage your account information and profile picture</p>
      </div>

      {/* Avatar Section */}
      <div className="mb-8 pb-8 border-b border-slate-700">
        <h3 className="text-lg font-semibold text-white mb-4">Profile Picture</h3>

        <div className="flex items-start gap-6">
          {/* Avatar Display */}
          <div className="relative">
            <div
              onClick={handleAvatarClick}
              className="w-32 h-32 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center cursor-pointer hover:opacity-80 transition-opacity overflow-hidden"
            >
              {avatar ? (
                <img src={avatar} alt="Avatar" className="w-full h-full object-cover" />
              ) : (
                <div className="text-center">
                  <Camera className="w-8 h-8 text-white mx-auto mb-2" />
                  <span className="text-xs text-white font-medium">
                    {user?.username?.charAt(0).toUpperCase()}
                  </span>
                </div>
              )}
            </div>

            {/* Upload Button Overlay */}
            <button
              onClick={handleAvatarClick}
              className="absolute bottom-0 right-0 bg-blue-600 hover:bg-blue-700 text-white p-2 rounded-full shadow-lg transition-colors"
            >
              <Upload className="w-4 h-4" />
            </button>
          </div>

          {/* Avatar Info */}
          <div className="flex-1">
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              onChange={handleFileChange}
              className="hidden"
            />

            <p className="text-gray-300 mb-2">
              <strong>Current User:</strong> {user?.username}
            </p>
            <p className="text-gray-400 text-sm mb-4">
              Click the camera icon or the image to upload a new profile picture
            </p>

            <ul className="text-xs text-gray-400 space-y-1 ml-4 list-disc">
              <li>Recommended: Square image (e.g., 500x500px)</li>
              <li>Maximum file size: 5MB</li>
              <li>Supported formats: JPG, PNG, WebP, GIF</li>
            </ul>
          </div>
        </div>
      </div>

      {/* Profile Information */}
      <div className="space-y-6">
        {/* Full Name */}
        <div>
          <label className="block">
            <div className="flex items-center gap-2 mb-2">
              <span className="font-semibold text-white">Full Name</span>
              <span className="text-gray-500 text-sm">(Optional)</span>
            </div>
            <p className="text-sm text-gray-400 mb-3">Your display name across the application</p>

            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="Enter your full name"
              maxLength={100}
              className="w-full px-4 py-2 bg-slate-700 border border-slate-600 text-white rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent placeholder-gray-500"
            />
            <p className="text-xs text-gray-500 mt-2">{fullName.length}/100 characters</p>
          </label>
        </div>

        {/* Email */}
        <div>
          <label className="block">
            <div className="flex items-center gap-2 mb-2">
              <span className="font-semibold text-white">Email Address</span>
              <span className="text-red-400">*</span>
            </div>
            <p className="text-sm text-gray-400 mb-3">Your account email address</p>

            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="your.email@example.com"
              className="w-full px-4 py-2 bg-slate-700 border border-slate-600 text-white rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent placeholder-gray-500"
            />
          </label>
        </div>

        {/* Username (Read-only) */}
        <div>
          <label className="block">
            <div className="flex items-center gap-2 mb-2">
              <span className="font-semibold text-white">Username</span>
              <span className="text-gray-500 text-xs bg-slate-700 px-2 py-1 rounded">READ-ONLY</span>
            </div>
            <p className="text-sm text-gray-400 mb-3">Your unique username cannot be changed</p>

            <input
              type="text"
              value={user?.username || ''}
              disabled
              className="w-full px-4 py-2 bg-slate-700 border border-slate-600 text-gray-400 rounded-lg cursor-not-allowed opacity-60"
            />
          </label>
        </div>

        {/* Member Since */}
        <div>
          <label className="block">
            <div className="flex items-center gap-2 mb-2">
              <span className="font-semibold text-white">Member Since</span>
            </div>

            <input
              type="text"
              value={
                user?.created_at
                  ? new Date(user.created_at).toLocaleDateString('en-US', {
                      year: 'numeric',
                      month: 'long',
                      day: 'numeric',
                    })
                  : 'Loading...'
              }
              disabled
              className="w-full px-4 py-2 bg-slate-700 border border-slate-600 text-gray-400 rounded-lg cursor-not-allowed opacity-60"
            />
          </label>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="mt-8 flex gap-3 pt-6 border-t border-slate-700">
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-6 py-2 bg-blue-600 text-white font-semibold rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
        >
          <Check className="w-4 h-4" />
          {saving ? 'Saving...' : 'Save Profile'}
        </button>
        <button
          onClick={handleReset}
          disabled={saving}
          className="px-6 py-2 bg-slate-700 text-white font-semibold rounded-lg hover:bg-slate-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
        >
          <X className="w-4 h-4" />
          Reset
        </button>
      </div>

      {/* Info Box */}
      <div className="mt-6 p-4 bg-blue-900 border border-blue-700 rounded-lg">
        <h4 className="font-semibold text-blue-200 mb-2">💡 Privacy Note</h4>
        <p className="text-sm text-blue-100">
          Your profile information is private and only visible to you. Email is used for account recovery and notifications.
        </p>
      </div>
    </div>
  );
};
