from flask import Flask, render_template, request, jsonify, send_file, url_for, redirect, session, flash
import os
import base64
import csv
import hashlib
import uuid
import json
from PIL import Image
import io
from main import get_math_explanation, create_video_from_steps
from werkzeug.utils import secure_filename
from google import genai
from google.genai import types
from functools import wraps
from youtube_utils import get_playlist_videos, COURSE_PLAYLISTS

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'videos')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['SECRET_KEY'] = 'your_secret_key_here'

# Path to the CSV file for user data
USERS_FILE = 'users.csv'

# Create users.csv if it doesn't exist
def init_users_file():
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['id', 'name', 'email', 'password'])

init_users_file()

# Hash password function
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# User authentication functions
def get_user_by_email(email):
    with open(USERS_FILE, 'r', newline='') as file:
        reader = csv.DictReader(file)
        for user in reader:
            if user['email'] == email:
                return user
    return None

def add_user(name, email, password):
    user_id = str(uuid.uuid4())
    hashed_password = hash_password(password)
    
    with open(USERS_FILE, 'a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([user_id, name, email, hashed_password])
    
    return user_id

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# Initialize Gemini
client = genai.Client(api_key="AIzaSyB_W9t18sgLbGXoD_zeqPaLkF8oyPPO19g")

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect('/home')
    return redirect('/login')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not email or not password:
            flash('Please fill in all fields', 'error')
            return render_template('login.html')
        
        user = get_user_by_email(email)
        
        if user and user['password'] == hash_password(password):
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            return redirect('/home')
        else:
            flash('Invalid email or password', 'error')
            return render_template('login.html')
    
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if not name or not email or not password or not confirm_password:
            flash('Please fill in all fields', 'error')
            return render_template('signup.html')
        
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('signup.html')
        
        existing_user = get_user_by_email(email)
        if existing_user:
            flash('Email already exists', 'error')
            return render_template('signup.html')
        
        user_id = add_user(name, email, password)
        session['user_id'] = user_id
        session['user_name'] = name
        
        return redirect('/home')
    
    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/home')
@login_required
def home():
    return render_template('home.html', user_name=session.get('user_name', ''))

@app.route('/tutor')
@login_required
def tutor():
    # Pass active_section to ensure the correct section is shown
    return render_template('index.html', 
                           active_section='tutor', 
                           show_tutor=True,
                           user_name=session.get('user_name', ''))

@app.route('/whiteboard')
@login_required
def whiteboard():
    # Pass active_section to ensure the correct section is shown
    return render_template('index.html', 
                           active_section='whiteboard', 
                           show_whiteboard=True,
                           user_name=session.get('user_name', ''))

@app.route('/graphing')
@login_required
def graphing():
    # Pass active_section to ensure the correct section is shown
    return render_template('index.html', 
                           active_section='graphing', 
                           show_graphing=True,
                           user_name=session.get('user_name', ''))

@app.route('/course/<topic>')
@login_required
def course(topic):
    # Convert hyphens to underscores for internal processing
    topic_key = topic.replace('-', '_')
    valid_topics = ['probability', 'trigonometry', 'polynomials', 'sets', 'calculus', 'number_system']
    
    if topic_key not in valid_topics:
        return redirect('/home')
    
    # Get user progress from session or initialize if not exists
    user_id = session.get('user_id')
    progress_file = f'user_progress_{user_id}.json'
    
    if os.path.exists(progress_file):
        with open(progress_file, 'r') as f:
            user_progress = json.load(f)
    else:
        user_progress = {}
    
    if topic_key not in user_progress:
        user_progress[topic_key] = {'completed': [], 'current_video': ''}
    
    # Get playlist data
    playlist_url = COURSE_PLAYLISTS[topic_key]
    try:
        playlist_data = get_playlist_videos(playlist_url)
        
        # Calculate progress percentage
        total_videos = len(playlist_data['videos'])
        completed_count = len(user_progress[topic_key]['completed'])
        
        # Ensure we have a valid calculation and default to 0 if there are no videos
        if total_videos > 0 and completed_count > 0:
            progress_percentage = int((completed_count / total_videos) * 100)
        else:
            progress_percentage = 0
            
        print(f"Progress for {topic_key}: {completed_count}/{total_videos} = {progress_percentage}%")
        
        # Set current video if not set
        current_video = user_progress[topic_key]['current_video']
        if not current_video and playlist_data['videos']:
            current_video = playlist_data['videos'][0]['id']
            user_progress[topic_key]['current_video'] = current_video
        
        # Save updated progress
        with open(progress_file, 'w') as f:
            json.dump(user_progress, f)
        
        return render_template(
            'course.html', 
            topic=topic,
            topic_title=topic_key.replace('_', ' ').title(),
            playlist=playlist_data,
            current_video=current_video,
            completed=user_progress[topic_key]['completed'],
            progress_percentage=progress_percentage,
            user_name=session.get('user_name', '')
        )
    except Exception as e:
        print(f"Error fetching playlist: {e}")
        return render_template('course.html', topic=topic, error=True, user_name=session.get('user_name', ''))

@app.route('/update_progress', methods=['POST'])
@login_required
def update_progress():
    data = request.json
    topic = data.get('topic')
    video_id = data.get('video_id')
    completed = data.get('completed', False)
    
    if not topic or not video_id:
        return jsonify({'error': 'Missing topic or video_id'}), 400
    
    # Convert hyphens to underscores for internal processing
    topic_key = topic.replace('-', '_')
    
    # Get user progress
    user_id = session.get('user_id')
    progress_file = f'user_progress_{user_id}.json'
    
    if os.path.exists(progress_file):
        with open(progress_file, 'r') as f:
            user_progress = json.load(f)
    else:
        user_progress = {}
    
    if topic_key not in user_progress:
        user_progress[topic_key] = {'completed': [], 'current_video': ''}
    
    # Update completed videos list
    if completed and video_id not in user_progress[topic_key]['completed']:
        user_progress[topic_key]['completed'].append(video_id)
    elif not completed and video_id in user_progress[topic_key]['completed']:
        user_progress[topic_key]['completed'].remove(video_id)
    
    # Update current video
    user_progress[topic_key]['current_video'] = video_id
    
    # Save updated progress
    with open(progress_file, 'w') as f:
        json.dump(user_progress, f)
    
    # Calculate progress percentage
    try:
        playlist_data = get_playlist_videos(COURSE_PLAYLISTS[topic_key])
        total_videos = len(playlist_data['videos'])
        completed_count = len(user_progress[topic_key]['completed'])
        
        # Ensure we have a valid calculation and default to 0 if there are no videos
        if total_videos > 0 and completed_count > 0:
            progress_percentage = int((completed_count / total_videos) * 100)
        else:
            progress_percentage = 0
            
        print(f"Update progress for {topic_key}: {completed_count}/{total_videos} = {progress_percentage}%")
    except Exception as e:
        print(f"Error calculating progress: {e}")
        progress_percentage = 0
    
    return jsonify({
        'success': True,
        'progress_percentage': progress_percentage
    })

@app.route('/analyze_whiteboard', methods=['POST'])
def analyze_whiteboard():
    try:
        # Get the image data and query from the request
        data = request.json
        image_data = data.get('image')
        query = data.get('query')

        if not image_data or not query:
            return jsonify({'error': 'Missing image or query'}), 400

        # Convert base64 image to PIL Image
        image_data = image_data.split(',')[1]  # Remove data URL prefix
        image_bytes = base64.b64decode(image_data)
        image = Image.open(io.BytesIO(image_bytes))

        # Generate response using Gemini
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                image,
                "You are a helpful math tutor. Analyze the whiteboard content and answer the following question: " + query
            ],
            config=types.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=1000
            )
        )

        return jsonify({'response': response.text})

    except Exception as e:
        print(f"Error in analyze_whiteboard: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/explain', methods=['POST'])
def explain():
    try:
        question = request.form.get('question')
        if not question:
            return jsonify({'error': 'No question provided'}), 400

        # Get explanation steps
        steps = get_math_explanation(question)
        
        # Generate a secure filename
        safe_filename = secure_filename(question[:30].replace(' ', '_'))
        video_filename = f'explanation_{safe_filename}.mp4'
        video_path = os.path.join(app.config['UPLOAD_FOLDER'], video_filename)
        
        # Generate video
        create_video_from_steps(steps, video_path)
        
        # Create URL for video
        video_url = url_for('static', filename=f'videos/{video_filename}')
        
        # Prepare response
        response = {
            'steps': steps,
            'video_path': video_url
        }
        
        return jsonify(response)
    
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True) 