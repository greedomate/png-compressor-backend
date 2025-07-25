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
        },
        'compress_parameters': {
            'file': 'PNG file to compress (required)',
            'mode': 'Compression mode: "lossless" or "lossy" (default: "lossless")',
            'analysis': 'Analysis mode: "true" for testing, "false" for actual compression (default: "false")',
            'optimize': 'Optimization level 0-9 for lossless mode (default: 6)',
            'colors': 'Number of colors 2-256 for lossy mode (default: 256)'
        }
    })

@app.route('/health')
def health():
    return jsonify({'status': 'healthy'})

@app.route('/compress', methods=['POST'])
def compress_png():
    try:
        # Get analysis parameter first for logging
        analysis = request.form.get('analysis', 'false').lower() == 'true'
        request_type = "ANALYSIS" if analysis else "COMPRESSION"
        
        # Log the request type clearly
        print(f"=== {request_type} REQUEST STARTED ===")
        print(f"Request Type: {request_type}")
        print(f"Analysis Parameter: {analysis}")
        
        # Check if file was uploaded
        if 'file' not in request.files:
            print(f"=== {request_type} REQUEST FAILED: No file provided ===")
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            print(f"=== {request_type} REQUEST FAILED: No file selected ===")
            return jsonify({'error': 'No file selected'}), 400
        
        # Check if file is PNG
        if not file.filename.lower().endswith('.png'):
            print(f"=== {request_type} REQUEST FAILED: Not a PNG file ===")
            return jsonify({'error': 'Only PNG files are supported'}), 400
        
        # Get compression mode (default to lossless)
        mode = request.form.get('mode', 'lossless')
        
        # Get original file size
        file.seek(0, 2)  # Seek to end
        original_size = file.tell()
        file.seek(0)  # Reset to beginning
        
        request_type = "analysis" if analysis else "compression"
        print(f"Starting {mode} {request_type}")
        print(f"Original file size: {original_size} bytes")
        
        if analysis:
            # Analysis mode: Quick compression test for size estimation
            print(f"Running quick analysis for {mode} mode")
            
            # For analysis, we can use faster settings
            if mode == 'lossless':
                # Use lower optimization for faster analysis
                optimize = int(request.form.get('optimize', 6))
                optimize = max(0, min(9, optimize))
                
                # Quick lossless test - just get the size
                output_buffer = io.BytesIO()
                image = Image.open(file.stream)
                
                # Minimal processing for analysis
                if image.mode not in ('RGBA', 'LA', 'P', 'RGB'):
                    image = image.convert('RGB')
                
                image.save(
                    output_buffer,
                    format='PNG',
                    optimize=True,
                    compress_level=min(optimize, 6)  # Cap at 6 for faster analysis
                )
                
            elif mode == 'lossy':
                # Quick lossy test with reduced colors for faster analysis
                colors = int(request.form.get('colors', 256))
                colors = max(2, min(256, colors))
                
                output_buffer = io.BytesIO()
                image = Image.open(file.stream)
                
                # Simplified lossy processing for analysis
                if image.mode in ('RGBA', 'LA'):
                    if image.mode == 'LA':
                        image = image.convert('RGBA')
                    image = image.quantize(colors=colors, dither=Image.Dither.FLOYDSTEINBERG)
                else:
                    if image.mode != 'RGB':
                        image = image.convert('RGB')
                    image = image.quantize(colors=colors, dither=Image.Dither.FLOYDSTEINBERG)
                
                image.save(output_buffer, format='PNG', optimize=True)
                
            else:
                return jsonify({'error': 'Invalid mode. Use "lossless" or "lossy"'}), 400
                
        else:
            # Compression mode: Full processing for actual compression
            print(f"Running full compression for {mode} mode")
            
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
                
                # Use floyd-steinberg as default (best quality for most images)
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
        print(f"Request type: {request_type}")
        
        if analysis:
            print(f"=== {request_type} REQUEST COMPLETED: Returning JSON data ===")
        else:
            print(f"=== {request_type} REQUEST COMPLETED: Returning compressed file ===")
        
        if analysis:
            # Analysis mode: Return JSON with compression data for comparison
            # Convert bytes to human readable format
            def format_size(size_bytes):
                if size_bytes < 1024:
                    return f"{size_bytes}B"
                elif size_bytes < 1024 * 1024:
                    return f"{size_bytes / 1024:.1f}KB"
                else:
                    return f"{size_bytes / (1024 * 1024):.1f}MB"
            
            return jsonify({
                'analysis': True,
                'original_size': original_size,
                'original_size_formatted': format_size(original_size),
                'compressed_size': compressed_size,
                'compressed_size_formatted': format_size(compressed_size),
                'compression_ratio': round(compression_ratio, 2),
                'mode': mode,
                'message': 'Analysis completed - use this data for smart recommendations'
            })
        else:
            # Compression mode: Return the actual compressed file
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
        print(f"=== {request_type} REQUEST FAILED: {e} ===")
        return jsonify({
            'error': 'Compression failed',
            'details': str(e)
        }), 500

if __name__ == '__main__':
    # Get port from environment variable (for production) or use 5000
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port) 