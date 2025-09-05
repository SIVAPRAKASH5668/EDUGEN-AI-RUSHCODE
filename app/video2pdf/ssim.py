import cv2
import os
import numpy as np
from skimage.metrics import structural_similarity as ssim

def create_video_folders(video_path):
    """
    Create the necessary directories to save frames and frames with changes.
    """
    video_name = os.path.splitext(os.path.basename(video_path))[0]
    base_folder = os.path.join("frames", video_name)

    # Create parent directory for this video
    if not os.path.exists(base_folder):
        os.makedirs(base_folder)

    # Create subdirectories for frames and frames_with_changes
    frames_folder = os.path.join(base_folder, "frames")
    frames_with_changes_folder = os.path.join(base_folder, "frames_with_changes")

    if not os.path.exists(frames_folder):
        os.makedirs(frames_folder)
    
    if not os.path.exists(frames_with_changes_folder):
        os.makedirs(frames_with_changes_folder)

    return frames_folder, frames_with_changes_folder

def extract_frames(video_path, fps=1):
    """
    Extract frames from the video and save them in the frames folder.
    """
    frames_folder, _ = create_video_folders(video_path)

    video_capture = cv2.VideoCapture(video_path)
    if not video_capture.isOpened():
        print("Error: Couldn't open video file.")
        return []

    total_frames = int(video_capture.get(cv2.CAP_PROP_FRAME_COUNT))
    video_fps = video_capture.get(cv2.CAP_PROP_FPS)
    frame_interval = int(video_fps // fps)

    frames = []
    frame_num = 0
    while True:
        ret, frame = video_capture.read()
        if not ret:
            break

        if frame_num % frame_interval == 0:
            frame_filename = os.path.join(frames_folder, f"frame_{frame_num:04d}.jpg")
            cv2.imwrite(frame_filename, frame)  # Save the frame to the frames folder
            frames.append(frame)

        frame_num += 1

    video_capture.release()
    return frames

def detect_slide_changes(frames, similarity_threshold=0.9):
    """
    Detect slide changes using SSIM between consecutive frames.
    """
    previous_frame = None
    slide_changes = []

    # Always consider the first frame as a change
    slide_changes.append(0)

    for i in range(1, len(frames)):
        current_frame = cv2.cvtColor(frames[i], cv2.COLOR_BGR2GRAY)
        if previous_frame is not None:
            score, _ = ssim(previous_frame, current_frame, full=True)
            if score < similarity_threshold:  # Threshold to detect significant changes
                slide_changes.append(i)
        previous_frame = current_frame

    return slide_changes

def save_detected_frames(frames, slide_changes, video_path):
    """
    Save frames that are detected as new slides in the frames_with_changes folder.
    """
    _, frames_with_changes_folder = create_video_folders(video_path)

    for i in slide_changes:
        frame_filename = os.path.join(frames_with_changes_folder, f"slide_{i:04d}.jpg")
        cv2.imwrite(frame_filename, frames[i])

    print(f"Detected {len(slide_changes)} slide changes and saved corresponding frames.")

# Example usage:
video_path = "videos/ppt1.mp4"  # Replace with your video file path
fps = 1  # Adjust this to extract frames at a particular rate (1 FPS)

# Step 1: Extract frames and save them in the frames folder
frames = extract_frames(video_path, fps)

# Step 2: Detect slide changes by comparing frames
slide_changes = detect_slide_changes(frames, similarity_threshold=0.85)

# Step 3: Save frames with detected slide changes in frames_with_changes folder
save_detected_frames(frames, slide_changes, video_path)
