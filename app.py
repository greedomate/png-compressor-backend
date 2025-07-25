from flask import Flask, request, send_file, jsonify
import os
import subprocess
import tempfile
from werkzeug.utils import secure_filename

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
        
        # Save uploaded file
        filename = secure_filename(file.filename)
        input_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(input_path)
        
        # Create output filename
        name, ext = os.path.splitext(filename)
        output_filename = f"{name}_compressed{ext}"
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)
        
        # Get compression method from request (default to oxipng)
        method = request.form.get('method', 'oxipng')
        
        if method == 'oxipng':
            # Use oxipng for compression
            result = subprocess.run([
                'oxipng', 
                '--opt', 'max',  # Maximum optimization
                '--strip', 'safe',  # Strip metadata
                '--out', output_path,
                input_path
            ], capture_output=True, text=True)
        elif method == 'pngquant':
            # Use pngquant for compression
            result = subprocess.run([
                'pngquant',
                '--quality=65-80',  # Quality range
                '--strip',  # Strip metadata
                '--force',
                '--output', output_path,
                input_path
            ], capture_output=True, text=True)
        else:
            return jsonify({'error': 'Invalid compression method. Use "oxipng" or "pngquant"'}), 400
        
        if result.returncode != 0:
            return jsonify({
                'error': 'Compression failed',
                'details': result.stderr
            }), 500
        
        # Get file sizes for comparison
        original_size = os.path.getsize(input_path)
        compressed_size = os.path.getsize(output_path)
        compression_ratio = ((original_size - compressed_size) / original_size) * 100
        
        # Clean up original file
        os.remove(input_path)
        
        # Return compressed file
        return send_file(
            output_path,
            as_attachment=True,
            download_name=output_filename,
            mimetype='image/png'
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000) 