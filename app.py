from flask import Flask, request, send_file, jsonify
import os
import tempfile
from werkzeug.utils import secure_filename
from PIL import Image
import io
import logging

app = Flask(__name__)

# Configure logging to show in Render
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
            'analyze_png_batch': '/analyze-png-batch',
            'health': '/health'
        },
        'compress_parameters': {
            'file': 'PNG file to compress (required)',
            'mode': 'Compression mode: "lossy" (default: "lossy")',
            'analysis': 'Analysis mode: "true" for testing, "false" for actual compression (default: "false")',
            'colors': 'Number of colors 2-256 for lossy mode (default: 256)'
        },
        'batch_analysis_parameters': {
            'file': 'PNG file to analyze (required)',
            'color_counts': 'Comma-separated color counts to test (e.g., "32,64,128")'
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
        logger.info(f"=== {request_type} REQUEST STARTED ===")
        logger.info(f"Request Type: {request_type}")
        logger.info(f"Analysis Parameter: {analysis}")
        
        # Check if file was uploaded
        if 'file' not in request.files:
            logger.error(f"=== {request_type} REQUEST FAILED: No file provided ===")
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            logger.error(f"=== {request_type} REQUEST FAILED: No file selected ===")
            return jsonify({'error': 'No file selected'}), 400
        
        # Check if file is PNG (validate by content, not just extension)
        def is_png_file(file):
            # Check file signature (PNG magic bytes)
            file.seek(0)
            signature = file.read(8)
            file.seek(0)  # Reset position
            return signature.startswith(b'\x89PNG\r\n\x1a\n')
        
        if not is_png_file(file):
            logger.error(f"=== {request_type} REQUEST FAILED: Not a PNG file (invalid content) ===")
            return jsonify({'error': 'Only PNG files are supported'}), 400
        
        # Get compression mode (default to lossy)
        mode = request.form.get('mode', 'lossy')
        
        # Get original file size
        file.seek(0, 2)  # Seek to end
        original_size = file.tell()
        file.seek(0)  # Reset to beginning
        
        request_type = "analysis" if analysis else "compression"
        logger.info(f"Starting {mode} {request_type}")
        logger.info(f"Original file size: {original_size} bytes")
        
        if analysis:
            # Analysis mode: Quick compression test for size estimation
            logger.info(f"Running quick analysis for {mode} mode")
            
            # For analysis, we can use faster settings
            if mode == 'lossy':
                # Quick lossy test with reduced colors for faster analysis
                colors = int(request.form.get('colors', 256))
                colors = max(2, min(256, colors))
                
                output_buffer = io.BytesIO()
                image = Image.open(file.stream)
                
                # For analysis, resize large images to speed up processing
                max_analysis_size = 800  # Max dimension for analysis
                if max(image.size) > max_analysis_size:
                    # Calculate new size maintaining aspect ratio
                    ratio = max_analysis_size / max(image.size)
                    new_size = (int(image.size[0] * ratio), int(image.size[1] * ratio))
                    image = image.resize(new_size, Image.Resampling.LANCZOS)
                    logger.info(f"Resized image to {new_size} for faster analysis")
                
                # Use faster dithering for analysis
                if image.mode in ('RGBA', 'LA'):
                    if image.mode == 'LA':
                        image = image.convert('RGBA')
                    image = image.quantize(colors=colors, dither=Image.Dither.ORDERED)  # Faster than FLOYDSTEINBERG
                else:
                    if image.mode != 'RGB':
                        image = image.convert('RGB')
                    image = image.quantize(colors=colors, dither=Image.Dither.ORDERED)  # Faster than FLOYDSTEINBERG
                
                # Use lower optimization for faster analysis
                image.save(output_buffer, format='PNG', optimize=False)  # No optimization for speed
                
            else:
                return jsonify({'error': 'Invalid mode. Use "lossy"'}), 400
                
        else:
            # Compression mode: Full processing for actual compression
            logger.info(f"Running full compression for {mode} mode")
        
        # Open the uploaded image
        image = Image.open(file.stream)
        
        # Create output buffer
        output_buffer = io.BytesIO()
        
        if mode == 'lossy':
            # Lossy compression - reduce colors
            colors = int(request.form.get('colors', 256))
            colors = max(2, min(256, colors))  # Ensure colors is between 2-256
            
            # Use floyd-steinberg as default (best quality for most images)
            dither = 'floyd-steinberg'
            
            logger.info(f"Lossy mode - colors: {colors}, dither: {dither}")
            
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
            return jsonify({'error': 'Invalid mode. Use "lossy"'}), 400
        
        # Get the compressed data
        output_buffer.seek(0)
        compressed_data = output_buffer.getvalue()
        
        # Calculate compression ratio
        compressed_size = len(compressed_data)
        compression_ratio = ((original_size - compressed_size) / original_size) * 100
        
        logger.info(f"Compressed size: {compressed_size} bytes")
        logger.info(f"Compression ratio: {compression_ratio:.2f}%")
        logger.info(f"Mode: {mode}")
        logger.info(f"Request type: {request_type}")
        
        if analysis:
            logger.info(f"=== {request_type} REQUEST COMPLETED: Returning JSON data ===")
        else:
            logger.info(f"=== {request_type} REQUEST COMPLETED: Returning compressed file ===")
        
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
        logger.error(f"=== {request_type} REQUEST FAILED: {e} ===")
        return jsonify({
            'error': 'Compression failed',
            'details': str(e)
        }), 500

@app.route('/analyze-png-batch', methods=['POST'])
def analyze_png_batch():
    """
    Batch analysis endpoint for smart analysis
    Tests multiple color counts in a single request for faster analysis
    """
    try:
        logger.info("=== BATCH ANALYSIS REQUEST STARTED ===")
        
        # Check if file was uploaded
        if 'file' not in request.files:
            logger.error("=== BATCH ANALYSIS REQUEST FAILED: No file provided ===")
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            logger.error("=== BATCH ANALYSIS REQUEST FAILED: No file selected ===")
            return jsonify({'error': 'No file selected'}), 400
        
        # Check if file is PNG (validate by content, not just extension)
        def is_png_file(file):
            # Check file signature (PNG magic bytes)
            file.seek(0)
            signature = file.read(8)
            file.seek(0)  # Reset position
            return signature.startswith(b'\x89PNG\r\n\x1a\n')
        
        if not is_png_file(file):
            logger.error("=== BATCH ANALYSIS REQUEST FAILED: Not a PNG file (invalid content) ===")
            return jsonify({'error': 'Only PNG files are supported'}), 400
        
        # Get color counts array
        color_counts_str = request.form.get('color_counts', '')
        if not color_counts_str:
            logger.error("=== BATCH ANALYSIS REQUEST FAILED: No color_counts provided ===")
            return jsonify({'error': 'color_counts parameter is required'}), 400
        
        try:
            color_counts = [int(x.strip()) for x in color_counts_str.split(',')]
            # Validate color counts
            for count in color_counts:
                if count < 2 or count > 256:
                    logger.error(f"=== BATCH ANALYSIS REQUEST FAILED: Invalid color count {count} ===")
                    return jsonify({'error': f'Color count {count} must be between 2 and 256'}), 400
        except ValueError:
            logger.error("=== BATCH ANALYSIS REQUEST FAILED: Invalid color_counts format ===")
            return jsonify({'error': 'color_counts must be comma-separated integers'}), 400
        
        # Get original file size
        file.seek(0, 2)  # Seek to end
        original_size = file.tell()
        file.seek(0)  # Reset to beginning
        
        logger.info(f"Batch analysis for {len(color_counts)} color counts: {color_counts}")
        logger.info(f"Original file size: {original_size} bytes")
        
        # Open the image once
        image = Image.open(file.stream)
        
        # For batch analysis, resize large images to speed up processing
        max_analysis_size = 800  # Max dimension for analysis
        if max(image.size) > max_analysis_size:
            # Calculate new size maintaining aspect ratio
            ratio = max_analysis_size / max(image.size)
            new_size = (int(image.size[0] * ratio), int(image.size[1] * ratio))
            image = image.resize(new_size, Image.Resampling.LANCZOS)
            logger.info(f"Resized image to {new_size} for faster batch analysis")
        
        results = []
        
        # Convert bytes to human readable format
        def format_size(size_bytes):
            if size_bytes < 1024:
                return f"{size_bytes}B"
            elif size_bytes < 1024 * 1024:
                return f"{size_bytes / 1024:.1f}KB"
            else:
                return f"{size_bytes / (1024 * 1024):.1f}MB"
        
        # Test each color count
        for color_count in color_counts:
            logger.info(f"Testing {color_count} colors...")
            
            # Create a copy of the image for this test
            test_image = image.copy()
            
            # Create output buffer
            output_buffer = io.BytesIO()
            
            # Apply lossy compression with this color count
            if test_image.mode in ('RGBA', 'LA'):
                if test_image.mode == 'LA':
                    test_image = test_image.convert('RGBA')
                test_image = test_image.quantize(colors=color_count, dither=Image.Dither.ORDERED)  # Faster for analysis
            else:
                if test_image.mode != 'RGB':
                    test_image = test_image.convert('RGB')
                test_image = test_image.quantize(colors=color_count, dither=Image.Dither.ORDERED)  # Faster for analysis
            
            # Save as PNG (no optimization for speed)
            test_image.save(output_buffer, format='PNG', optimize=False)
            
            # Get compressed size
            output_buffer.seek(0)
            compressed_data = output_buffer.getvalue()
            compressed_size = len(compressed_data)
            compression_ratio = ((original_size - compressed_size) / original_size) * 100
            
            # Add result
            results.append({
                'color_count': color_count,
                'compressed_size': compressed_size,
                'compressed_size_formatted': format_size(compressed_size),
                'compression_ratio': round(compression_ratio, 2)
            })
            
            logger.info(f"  {color_count} colors: {format_size(compressed_size)} ({compression_ratio:.1f}% reduction)")
        
        logger.info("=== BATCH ANALYSIS REQUEST COMPLETED ===")
        
        return jsonify({
            'batch_analysis': True,
            'original_size': original_size,
            'original_size_formatted': format_size(original_size),
            'results': results,
            'message': 'Batch analysis completed - use results for smart recommendations'
        })
        
    except Exception as e:
        logger.error(f"=== BATCH ANALYSIS REQUEST FAILED: {e} ===")
        return jsonify({
            'error': 'Batch analysis failed',
            'details': str(e)
        }), 500

if __name__ == '__main__':
    # Get port from environment variable (for production) or use 5000
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port) 