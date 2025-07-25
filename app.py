from flask import Flask, request, send_file, jsonify
import os
import tempfile
from werkzeug.utils import secure_filename
from PIL import Image
import io

app = Flask(__name__)

# Configure upload folder
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

@app.route('/')
def home():
    return jsonify({
        'message': 'PNG Compressor Backend',
        'status': 'running',
        'endpoints': {
            'compress': '/compress',
            'health': '/health'
        }
    })

@app.route('/health')
def health():
    return jsonify({'status': 'healthy'})

@app.route('/compress', methods=['POST'])
def compress_png():
    try:
        # Check if file was uploaded
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Check if file is PNG
        if not file.filename.lower().endswith('.png'):
            return jsonify({'error': 'Only PNG files are supported'}), 400
        
        # Get compression quality from request (default to 85)
        quality = int(request.form.get('quality', 85))
        quality = max(1, min(100, quality))  # Ensure quality is between 1-100
        
        # Get optimization level from request (default to 6)
        optimize = int(request.form.get('optimize', 6))
        optimize = max(0, min(9, optimize))  # Ensure optimize is between 0-9
        
        print(f"Starting compression with quality: {quality}, optimize: {optimize}")
        
        # Open and compress the image using Pillow
        try:
            # Open the uploaded image
            image = Image.open(file.stream)
            
            # Convert to RGB if necessary (PNG with transparency will be preserved)
            if image.mode in ('RGBA', 'LA', 'P'):
                # Keep transparency for PNG
                pass
            elif image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Create output buffer
            output_buffer = io.BytesIO()
            
            # Save with compression settings
            image.save(
                output_buffer,
                format='PNG',
                optimize=True,
                compress_level=optimize
            )
            
            # Get the compressed data
            output_buffer.seek(0)
            compressed_data = output_buffer.getvalue()
            
            # Get original file size
            file.seek(0, 2)  # Seek to end
            original_size = file.tell()
            file.seek(0)  # Reset to beginning
            
            # Calculate compression ratio
            compressed_size = len(compressed_data)
            compression_ratio = ((original_size - compressed_size) / original_size) * 100
            
            print(f"Original size: {original_size} bytes")
            print(f"Compressed size: {compressed_size} bytes")
            print(f"Compression ratio: {compression_ratio:.2f}%")
            
            # Create output filename
            name, ext = os.path.splitext(secure_filename(file.filename))
            output_filename = f"{name}_compressed{ext}"
            
            # Return compressed file
            output_buffer.seek(0)
            return send_file(
                output_buffer,
                as_attachment=True,
                download_name=output_filename,
                mimetype='image/png'
            )
            
        except Exception as e:
            print(f"Image processing error: {e}")
            return jsonify({
                'error': 'Image processing failed',
                'details': str(e)
            }), 500
        
    except Exception as e:
        print(f"General error: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Get port from environment variable (for production) or use 5000
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port) 