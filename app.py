import os
from flask import Flask, render_template, request, jsonify
from threading import Thread, Lock
from pathlib import Path
import logging
import yt_dlp
import ffmpeg

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Store the download progress (for demo purposes)
download_progress = {}
progress_lock = Lock()

# Video information (store once the URL is fetched)
video_info = {}

def sanitize_filename(filename):
    """Sanitize filenames to make them compatible with Windows."""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    return filename

def download_video(url, output_path, title):
    """Download video using yt-dlp."""
    global download_progress
    actual_downloaded_file = None  # Initialize within the function scope
    with progress_lock:
        download_progress['progress'] = 0

    def progress_hook(d):
        """Hook to track download progress and fetch output file."""
        nonlocal actual_downloaded_file
        if d['status'] == 'finished':
            actual_downloaded_file = d['filename']  # Get the actual file name
            with progress_lock:
                download_progress['progress'] = 100
        elif d['status'] == 'downloading':
            total = d.get('total_bytes', 1)
            downloaded = d.get('downloaded_bytes', 0)
            if total > 0:
                with progress_lock:
                    download_progress['progress'] = int((downloaded / total) * 100)

    ydl_opts = {
        'format': 'bestvideo[height<=2160]+bestaudio/best[height<=2160]',  # Ensure max quality is 4K
        'outtmpl': str(output_path),
        'merge_output_format': 'mp4',
        'progress_hooks': [progress_hook],
        'windowsfilenames': True,  # Sanitize filenames for Windows
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        if actual_downloaded_file:
            sanitized_title = sanitize_filename(title)
            # Remove conversion system
            # converted_file = convert_video(Path(actual_downloaded_file), sanitized_title)
            # if converted_file:
            #     os.remove(actual_downloaded_file)  # Delete original file after conversion
        else:
            logging.error(f"Downloaded file not found: {output_path}")
            with progress_lock:
                download_progress['progress'] = -1  # Indicate error
    except Exception as e:
        logging.error(f"Error downloading video: {e}")
        with progress_lock:
            download_progress['progress'] = -1  # Indicate error

def format_numbers(num):
    """Convert numbers to a more readable format (K, M, B)."""
    if num >= 1_000_000_000:
        return f'{num / 1_000_000_000:.1f}B'  # Billions
    elif num >= 1_000_000:
        return f'{num / 1_000_000:.1f}M'  # Millions
    elif num >= 1_000:
        return f'{num / 1_000:.1f}K'  # Thousands
    else:
        return str(num)  # No conversion for numbers below 1000

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_video_info', methods=['POST'])
def get_video_info():
    global video_info
    try:
        video_url = request.json.get('video_url')
        if not video_url:
            return jsonify({'error': 'No video URL provided'})

        ydl_opts = {
            'quiet': True,
            'forcejson': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            video_info = {
                'title': info.get('title', 'No title'),
                'views': format_numbers(info.get('view_count', 0)),  # Format views
                'likes': format_numbers(info.get('like_count', 0)),  # Format likes
                'thumbnail_url': info.get('thumbnail', ''),
            }
        
        return jsonify(video_info)
    
    except Exception as e:
        logging.error(f"Error fetching video info: {e}")
        return jsonify({'error': str(e)})

@app.route('/download', methods=['POST'])
def download():
    global video_info
    try:
        video_url = request.json.get('video_url')
        if not video_url:
            return jsonify({'message': 'No video URL provided'})
        
        downloads_dir = os.path.join(os.path.expanduser("~"), "Downloads")
        download_folder = Path(f"{downloads_dir}/Youtube Videos/Papa")

        # Check if the folder exists, and create it if not
        if not download_folder.exists():
            download_folder.mkdir(parents=True, exist_ok=True)
        
        output_path = download_folder / '%(title)s.%(ext)s'
        
        # Start download in a separate thread to prevent blocking the server
        download_thread = Thread(target=download_video, args=(video_url, output_path, video_info.get('title', 'video')))
        download_thread.start()
        
        return jsonify({'message': 'Download started successfully!'})
    
    except Exception as e:
        logging.error(f"Error starting download: {e}")
        return jsonify({'message': str(e)})

@app.route('/get_download_progress', methods=['GET'])
def get_download_progress():
    with progress_lock:
        return jsonify(download_progress)

if __name__ == '__main__':
    app.run(debug=True, threaded=True)
