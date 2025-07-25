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
        
        # Get compression mode (default to lossless)
        mode = request.form.get('mode', 'lossless')
        
        # Get original file size
        file.seek(0, 2)  # Seek to end
        original_size = file.tell()
        file.seek(0)  # Reset to beginning
        
        print(f"Starting {mode} compression")
        print(f"Original file size: {original_size} bytes")
        
        # Open the uploaded image
        image = Image.open(file.stream)
        
        # Create output buffer
        output_buffer = io.BytesIO()
        
        if mode == 'lossless':
            # Lossless compression - preserve all colors
            optimize = int(request.form.get('optimize', 6))
            optimize = max(0, min(9, optimize))
            
            print(f"Lossless mode - optimize: {optimize}")
            
            # Convert to RGB if necessary (PNG with transparency will be preserved)
            if image.mode in ('RGBA', 'LA', 'P'):
                # Keep transparency for PNG
                pass
            elif image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Save with compression settings
            image.save(
                output_buffer,
                format='PNG',
                optimize=True,
                compress_level=optimize
            )
            
        elif mode == 'lossy':
            # Lossy compression - reduce colors
            colors = int(request.form.get('colors', 256))
            colors = max(2, min(256, colors))  # Ensure colors is between 2-256
            
            dither = request.form.get('dither', 'floyd-steinberg')
            valid_dithers = ['none', 'floyd-steinberg', 'ordered']
            if dither not in valid_dithers:
                dither = 'floyd-steinberg'
            
            print(f"Lossy mode - colors: {colors}, dither: {dither}")
            
            # Convert to palette mode with specified number of colors
            if image.mode in ('RGBA', 'LA'):
                # Handle transparency by converting to RGBA first
                if image.mode == 'LA':
                    image = image.convert('RGBA')
                # Convert to palette with transparency support
                if dither == 'none':
                    dither_attr = Image.Dither.NONE
                elif dither == 'floyd-steinberg':
                    dither_attr = Image.Dither.FLOYDSTEINBERG
                elif dither == 'ordered':
                    dither_attr = Image.Dither.ORDERED
                else:
                    dither_attr = Image.Dither.FLOYDSTEINBERG
                image = image.quantize(colors=colors, dither=dither_attr)
            else:
                # Convert to RGB first, then to palette
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                if dither == 'none':
                    dither_attr = Image.Dither.NONE
                elif dither == 'floyd-steinberg':
                    dither_attr = Image.Dither.FLOYDSTEINBERG
                elif dither == 'ordered':
                    dither_attr = Image.Dither.ORDERED
                else:
                    dither_attr = Image.Dither.FLOYDSTEINBERG
                image = image.quantize(colors=colors, dither=dither_attr)
            
            # Save as PNG
            image.save(
                output_buffer,
                format='PNG',
                optimize=True
            )
            
        else:
            return jsonify({'error': 'Invalid mode. Use "lossless" or "lossy"'}), 400
        
        # Get the compressed data
        output_buffer.seek(0)
        compressed_data = output_buffer.getvalue()
        
        # Calculate compression ratio
        compressed_size = len(compressed_data)
        compression_ratio = ((original_size - compressed_size) / original_size) * 100
        
        print(f"Compressed size: {compressed_size} bytes")
        print(f"Compression ratio: {compression_ratio:.2f}%")
        print(f"Mode: {mode}")
        
        # Create output filename
        name, ext = os.path.splitext(secure_filename(file.filename))
        output_filename = f"{name}_{mode}_compressed{ext}"
        
        # Return compressed file
        output_buffer.seek(0)
        return send_file(
            output_buffer,
            as_attachment=True,
            download_name=output_filename,
            mimetype='image/png'
        )
        
    except Exception as e:
        print(f"Compression error: {e}")
        return jsonify({
            'error': 'Compression failed',
            'details': str(e)
        }), 500

if __name__ == '__main__':
    # Get port from environment variable (for production) or use 5000
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port) 