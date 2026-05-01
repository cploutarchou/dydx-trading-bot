/**
 * Profile Settings Component
 * Allows users to manage their profile information and upload avatars
 */

import { useMutation } from '@tanstack/react-query';
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

const getErrorMessage = (error: unknown, fallback: string): string => {
  if (error instanceof Error) return error.message;
  if (typeof error === 'object' && error !== null) {
    const err = error as {
      response?: { data?: { detail?: string } };
      message?: string;
    };
    return err.response?.data?.detail || err.message || fallback;
  }
  return fallback;
};

export const ProfileSettings: React.FC<ProfileSettingsProps> = () => {
  const { user } = useAuthStore();
  const [fullName, setFullName] = useState(user?.full_name || '');
  const [email, setEmail] = useState(user?.email || '');
  const [avatar, setAvatar] = useState<string | null>(user?.avatar || null);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const updateProfileMutation = useMutation({
    mutationFn: (profileData: ProfileUpdateData) => apiClient.updateProfile(profileData),
  });

  useEffect(() => {
    setFullName(user?.full_name || '');
    setEmail(user?.email || '');
    setAvatar(user?.avatar || null);
  }, [user?.avatar, user?.email, user?.full_name]);

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
      setMessage(null);

      const profileData = {
        full_name: fullName || undefined,
        email,
        avatar: avatar || undefined,
      };

      // Call API to save profile
      const response = await updateProfileMutation.mutateAsync(profileData);

      if (response.success && response.data?.user) {
        const updatedUser = response.data.user;
        useAuthStore.setState({ user: updatedUser });

        setMessage({ type: 'success', text: 'Profile saved successfully' });
      } else {
        setMessage({
          type: 'error',
          text: response.message || 'Failed to save profile',
        });
      }
    } catch (error: unknown) {
      const errorMessage = getErrorMessage(error, 'Failed to save profile');
      setMessage({
        type: 'error',
        text: errorMessage,
      });
    }
  };

  const handleReset = () => {
    setFullName(user?.full_name || '');
    setEmail(user?.email || '');
    setAvatar(user?.avatar || null);
    setMessage(null);
  };

  const saving = updateProfileMutation.isPending;

  return (
    <div className="premium-panel p-6">
      {/* Message Display */}
      {message && (
        <div
          className={`mb-6 px-4 py-3 rounded border ${
            message.type === 'success'
              ? 'border-emerald-700/40 bg-emerald-900/20 text-emerald-200'
              : 'border-red-700/40 bg-red-900/20 text-red-200'
          }`}
        >
          {message.text}
        </div>
      )}

      {/* Section Header */}
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-white">Profile Settings</h2>
        <p className="mt-1 text-slate-400">Manage your account information and profile picture</p>
      </div>

      {/* Avatar Section */}
      <div className="mb-8 pb-8 border-b border-slate-700">
        <h3 className="text-lg font-semibold text-white mb-4">Profile Picture</h3>

        <div className="flex items-start gap-6">
          {/* Avatar Display */}
          <div className="relative">
            <div
              onClick={handleAvatarClick}
              className="flex h-32 w-32 cursor-pointer items-center justify-center overflow-hidden rounded-full bg-linear-to-br from-cyan-500 to-blue-600 transition-opacity hover:opacity-85"
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
              type="button"
              onClick={handleAvatarClick}
              className="absolute bottom-0 right-0 rounded-full bg-cyan-500 p-2 text-slate-900 shadow-lg transition-colors hover:bg-cyan-400"
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

            <p className="mb-2 text-slate-300">
              <strong>Current User:</strong> {user?.username}
            </p>
            <p className="mb-4 text-sm text-slate-400">
              Click the camera icon or the image to upload a new profile picture
            </p>

            <ul className="ml-4 list-disc space-y-1 text-xs text-slate-400">
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
              <span className="text-sm text-slate-500">(Optional)</span>
            </div>
            <p className="mb-3 text-sm text-slate-400">Your display name across the application</p>

            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="Enter your full name"
              maxLength={100}
              disabled={saving}
              className="premium-input"
            />
            <p className="mt-2 text-xs text-slate-500">{fullName.length}/100 characters</p>
          </label>
        </div>

        {/* Email */}
        <div>
          <label className="block">
            <div className="flex items-center gap-2 mb-2">
              <span className="font-semibold text-white">Email Address</span>
              <span className="text-red-400">*</span>
            </div>
            <p className="mb-3 text-sm text-slate-400">Your account email address</p>

            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="your.email@example.com"
              disabled={saving}
              className="premium-input"
            />
          </label>
        </div>

        {/* Username (Read-only) */}
        <div>
          <label className="block">
            <div className="flex items-center gap-2 mb-2">
              <span className="font-semibold text-white">Username</span>
              <span className="rounded bg-slate-800 px-2 py-1 text-xs text-slate-500 ring-1 ring-slate-700/60">
                READ-ONLY
              </span>
            </div>
            <p className="mb-3 text-sm text-slate-400">Your unique username cannot be changed</p>

            <input
              type="text"
              value={user?.username || ''}
              disabled
              className="premium-input cursor-not-allowed opacity-60"
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
              className="premium-input cursor-not-allowed opacity-60"
            />
          </label>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="mt-8 flex gap-3 pt-6 border-t border-slate-700">
        <button
          type="button"
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-2 rounded-xl bg-cyan-500 px-6 py-2 font-semibold text-slate-900 transition hover:bg-cyan-400 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Check className="w-4 h-4" />
          {saving ? 'Saving...' : 'Save Profile'}
        </button>
        <button
          type="button"
          onClick={handleReset}
          disabled={saving}
          className="flex items-center gap-2 rounded-xl border border-slate-700/70 bg-slate-900/70 px-6 py-2 font-semibold text-white transition hover:border-cyan-500/35 hover:bg-slate-900 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <X className="w-4 h-4" />
          Reset
        </button>
      </div>

      {/* Info Box */}
      <div className="mt-6 rounded-lg border border-cyan-700/40 bg-cyan-900/20 p-4">
        <h4 className="mb-2 font-semibold text-cyan-200">💡 Privacy Note</h4>
        <p className="text-sm text-cyan-100">
          Your profile information is private and only visible to you. Email is used for account
          recovery and notifications.
        </p>
      </div>
    </div>
  );
};
