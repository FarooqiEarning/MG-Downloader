import os
import yt_dlp
from flask import Flask, render_template, request, jsonify
from threading import Thread
from pathlib import Path

app = Flask(__name__)

# Store the download progress (for demo purposes)
download_progress = {}

# Video information (store once the URL is fetched)
video_info = {}

def download_video(url, output_path):
    global download_progress
    download_progress = {'progress': 0}
    
    # Define download options for yt-dlp
    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': output_path,
        'progress_hooks': [progress_hook],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

def progress_hook(d):
    """Function to track the download progress"""
    if d['status'] == 'downloading':
        total = d.get('total_bytes', 1)
        downloaded = d.get('downloaded_bytes', 0)
        if total > 0:
            download_progress['progress'] = int((downloaded / total) * 100)
    elif d['status'] == 'finished':
        download_progress['progress'] = 100

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
        return jsonify({'error': str(e)})

@app.route('/download', methods=['POST'])
def download():
    try:
        video_url = request.json.get('video_url')
        if not video_url:
            return jsonify({'message': 'No video URL provided'})
        
        # Get Document Dir
        downloads_dir = os.path.join(os.path.expanduser("~"), "Downloads")

        # Use f-string properly for the example folder path
        download_folder = Path(f"{downloads_dir}/Youtube Videos")

        # Check if the 'example' folder exists, and create it if not
        if not download_folder.exists():
            download_folder.mkdir(parents=True, exist_ok=True)
        
        output_path = os.path.join(download_folder, '%(title)s.%(ext)s')
        
        # Start download in a separate thread to prevent blocking the server
        download_thread = Thread(target=download_video, args=(video_url, output_path))
        download_thread.start()
        
        return jsonify({'message': 'Download started successfully!'})
    
    except Exception as e:
        return jsonify({'message': str(e)})

@app.route('/get_download_progress', methods=['GET'])
def get_download_progress():
    return jsonify(download_progress)

if __name__ == '__main__':
    if not os.path.exists('downloads'):
        os.makedirs('downloads')
    app.run(debug=True, threaded=True)
