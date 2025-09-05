import cv2
import os
import numpy as np
from skimage.metrics import structural_similarity as ssim

class VideoProcessor:
    def __init__(self, video_path):
        self.video_path = video_path
        self.video_name = os.path.splitext(os.path.basename(video_path))[0]
        self.base_folder = os.path.join("instance", "processed", self.video_name)
        self.frames_folder = os.path.join(self.base_folder, "frames")
        self.slides_folder = os.path.join(self.base_folder, "slides")
        
        # Create necessary directories
        os.makedirs(self.frames_folder, exist_ok=True)
        os.makedirs(self.slides_folder, exist_ok=True)

    def extract_frames(self, fps=1):
        video_capture = cv2.VideoCapture(self.video_path)
        if not video_capture.isOpened():
            raise ValueError("Couldn't open video file.")

        frames = []
        video_fps = video_capture.get(cv2.CAP_PROP_FPS)
        frame_interval = int(video_fps // fps) if video_fps > fps else 1
        
        frame_num = 0
        while True:
            ret, frame = video_capture.read()
            if not ret:
                break

            if frame_num % frame_interval == 0:
                frame_filename = os.path.join(self.frames_folder, f"frame_{frame_num:04d}.jpg")
                cv2.imwrite(frame_filename, frame)
                frames.append(frame)

            frame_num += 1

        video_capture.release()
        return frames

    def detect_slide_changes(self, frames, similarity_threshold=0.85):
        slide_changes = [0]  # Always include first frame
        previous_frame = None

        for i in range(1, len(frames)):
            # Convert frames to grayscale for comparison
            current_frame_gray = cv2.cvtColor(frames[i], cv2.COLOR_BGR2GRAY)
            
            if previous_frame is None:
                previous_frame = current_frame_gray
                continue
                
            # Ensure frames are the same size for SSIM
            if current_frame_gray.shape != previous_frame.shape:
                current_frame_gray = cv2.resize(current_frame_gray, (previous_frame.shape[1], previous_frame.shape[0]))
                
            # Calculate similarity
            score, _ = ssim(previous_frame, current_frame_gray, full=True)
            
            if score < similarity_threshold:
                slide_changes.append(i)
                
            previous_frame = current_frame_gray

        return slide_changes

    def save_detected_frames(self, frames, slide_changes):
        for i, frame_idx in enumerate(slide_changes):
            frame_filename = os.path.join(self.slides_folder, f"slide_{i:04d}.jpg")
            cv2.imwrite(frame_filename, frames[frame_idx])
        return self.slides_folder

    def process_video(self, fps=1, similarity_threshold=0.85):
        frames = self.extract_frames(fps)
        if not frames:
            raise ValueError("No frames were extracted from the video.")
            
        slide_changes = self.detect_slide_changes(frames, similarity_threshold)
        output_folder = self.save_detected_frames(frames, slide_changes)
        return output_folder