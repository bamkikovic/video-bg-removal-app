from flask import Flask, request, send_file, render_template
from rembg import remove
import os
import cv2
import numpy as np
import subprocess
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__, static_folder='static', template_folder='templates')
UPLOAD_FOLDER = 'uploads'
PROCESSED_FOLDER = 'processed'
FRAMES_FOLDER = 'frames'

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)
os.makedirs(FRAMES_FOLDER, exist_ok=True)

progress = {"value": 0}  # Global variable for tracking progress

def process_image(file_path):
    with open(file_path, "rb") as f:
        input_data = f.read()
    output_data = remove(input_data)
    output_path = os.path.join(PROCESSED_FOLDER, "output.png")
    with open(output_path, "wb") as f:
        f.write(output_data)
    return output_path

def extract_frames(video_path, frames_dir):
    # Resize video to 50% resolution and reduce frame rate to 15 fps
    subprocess.run([
        "ffmpeg", "-i", video_path,
        "-vf", "scale=iw*0.5:ih*0.5,fps=15",
        os.path.join(frames_dir, "frame_%04d.png")
    ], check=True)

def process_frames(frames_dir, processed_dir):
    global progress
    frames = sorted(os.listdir(frames_dir))
    total_frames = len(frames)

    def process_single_frame(frame):
        frame_path = os.path.join(frames_dir, frame)
        output_path = os.path.join(processed_dir, frame)
        with open(frame_path, "rb") as f:
            input_data = f.read()
        output_data = remove(input_data)
        with open(output_path, "wb") as f:
            f.write(output_data)

    # Use ThreadPoolExecutor for concurrent frame processing
    with ThreadPoolExecutor(max_workers=4) as executor:  # Adjust workers as per system capabilities
        for i, _ in enumerate(executor.map(process_single_frame, frames)):
            progress["value"] = int(((i + 1) / total_frames) * 100)

def reassemble_video(processed_dir, output_path, fps=15):
    # Reassemble frames into a video using ffmpeg
    subprocess.run([
        "ffmpeg", "-r", str(fps), "-i",
        os.path.join(processed_dir, "frame_%04d.png"),
        "-c:v", "libx264", "-vf", "fps=15", "-pix_fmt", "yuv420p", output_path
    ], check=True)

def process_video(file_path):
    global progress
    progress["value"] = 0  # Reset progress

    frames_dir = os.path.join(FRAMES_FOLDER, "frames")
    processed_dir = os.path.join(FRAMES_FOLDER, "processed")
    os.makedirs(frames_dir, exist_ok=True)
    os.makedirs(processed_dir, exist_ok=True)

    # Step 1: Extract frames
    extract_frames(file_path, frames_dir)

    # Step 2: Process frames
    process_frames(frames_dir, processed_dir)

    # Step 3: Reassemble video
    output_path = os.path.join(PROCESSED_FOLDER, "output.mp4")
    reassemble_video(processed_dir, output_path)

    # Clean up temporary frame directories
    for folder in [frames_dir, processed_dir]:
        for file in os.listdir(folder):
            os.remove(os.path.join(folder, file))
        os.rmdir(folder)

    progress["value"] = 100  # Ensure progress is set to 100% after completion
    return output_path

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    file = request.files['file']
    file_type = request.form.get('type')  # 'image' or 'video'
    save_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(save_path)

    if file_type == 'image':
        output_path = process_image(save_path)
    elif file_type == 'video':
        output_path = process_video(save_path)
    else:
        return "Invalid file type. Only images and videos are supported.", 400

    return send_file(output_path, as_attachment=True)

@app.route('/progress', methods=['GET'])
def get_progress():
    return {"progress": progress["value"]}

if __name__ == '__main__':
    from waitress import serve
    serve(app, host='0.0.0.0', port=8080)
