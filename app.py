import os
import io
from flask import Flask, render_template, request, redirect, url_for, send_file
from PIL import Image
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload size
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'resizer-app-secret-key')

# Create upload folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_image_size_kb(img, format):
    """Get image size in kilobytes"""
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format=format)
    return len(img_byte_arr.getvalue()) / 1024

def resize_image_to_size(image, min_size_kb, max_size_kb, format):
    """Resize image to fit within the specified size range"""
    # Make a copy of the image to avoid modifying the original
    img = image.copy()
    
    # Get current image size in KB
    current_size = get_image_size_kb(img, format)
    
    # If current size is already in range, return the image
    if min_size_kb <= current_size <= max_size_kb:
        return img
    
    # If current size is smaller than min_size_kb, we can't increase it
    if current_size < min_size_kb:
        # We could potentially increase quality but this might not always work well
        # For simplicity, we'll just return the original size
        return img
    
    # If current size is larger than max_size_kb, resize it
    width, height = img.size
    quality = 95  # Start with high quality
    
    # Binary search to find the optimal size/quality
    min_quality = 10
    max_quality = 95
    
    while current_size > max_size_kb and (width > 50 and height > 50):
        # Try reducing quality first
        if quality > min_quality:
            quality -= 5
        else:
            # If quality is at minimum, then reduce dimensions
            width = int(width * 0.9)
            height = int(height * 0.9)
            img = image.copy()
            img = img.resize((width, height), Image.LANCZOS)
        
        # Check new size
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format=format, quality=quality)
        current_size = len(img_byte_arr.getvalue()) / 1024
    
    return img

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/resize', methods=['POST'])
def resize():
    # Check if file part exists in the request
    if 'file' not in request.files:
        return redirect(request.url)
    
    file = request.files['file']
    
    # If user doesn't select file, browser also submits an empty file
    if file.filename == '':
        return redirect(request.url)
    
    if file and allowed_file(file.filename):
        # Get target size
        min_size_kb = float(request.form.get('min_size', 0))
        max_size_kb = float(request.form.get('max_size', 500))
        
        # Process and save the uploaded file
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        # Get file extension
        file_ext = filename.rsplit('.', 1)[1].lower()
        img_format = 'JPEG' if file_ext in ['jpg', 'jpeg'] else file_ext.upper()
        
        # Open and resize the image
        with Image.open(file_path) as img:
            # Convert to RGB if needed (for PNG with transparency)
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
                
            # Resize image
            resized_img = resize_image_to_size(img, min_size_kb, max_size_kb, img_format)
            
            # Save the resized image
            resized_filename = f"resized_{filename}"
            resized_path = os.path.join(app.config['UPLOAD_FOLDER'], resized_filename)
            resized_img.save(resized_path, format=img_format)
            
            # Get the final size for display
            final_size = os.path.getsize(resized_path) / 1024
            
            # Prepare the file for download
            return send_file(resized_path, as_attachment=True, download_name=resized_filename)
    
    return redirect(url_for('index'))

if __name__ == '__main__':
    # This is used when running locally only. When deploying to Render,
    # Render will use the gunicorn server specified in the render.yaml file
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
