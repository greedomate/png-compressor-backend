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

@app.route('/test-tools')
def test_tools():
    """Test if compression tools are available"""
    try:
        # Test oxipng
        oxipng_result = subprocess.run(['oxipng', '--version'], capture_output=True, text=True)
        
        # Test pngquant
        pngquant_result = subprocess.run(['pngquant', '--version'], capture_output=True, text=True)
        
        return jsonify({
            'oxipng': {
                'available': oxipng_result.returncode == 0,
                'version': oxipng_result.stdout.strip() if oxipng_result.returncode == 0 else 'Not found',
                'error': oxipng_result.stderr if oxipng_result.returncode != 0 else None
            },
            'pngquant': {
                'available': pngquant_result.returncode == 0,
                'version': pngquant_result.stdout.strip() if pngquant_result.returncode == 0 else 'Not found',
                'error': pngquant_result.stderr if pngquant_result.returncode != 0 else None
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
        
        print(f"Starting compression with method: {method}")
        print(f"Input file: {input_path}")
        print(f"Output file: {output_path}")
        
        # Check if compression tools are available
        try:
            if method == 'oxipng':
                # Check if oxipng is available
                check_result = subprocess.run(['oxipng', '--version'], capture_output=True, text=True)
                print(f"oxipng version check: {check_result.returncode}")
                print(f"oxipng stdout: {check_result.stdout}")
                print(f"oxipng stderr: {check_result.stderr}")
                
                # Use oxipng for compression
                result = subprocess.run([
                    'oxipng', 
                    '--opt', 'max',  # Maximum optimization
                    '--strip', 'safe',  # Strip metadata
                    '--out', output_path,
                    input_path
                ], capture_output=True, text=True)
            elif method == 'pngquant':
                # Check if pngquant is available
                check_result = subprocess.run(['pngquant', '--version'], capture_output=True, text=True)
                print(f"pngquant version check: {check_result.returncode}")
                print(f"pngquant stdout: {check_result.stdout}")
                print(f"pngquant stderr: {check_result.stderr}")
                
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
        except FileNotFoundError as e:
            print(f"Compression tool not found: {e}")
            return jsonify({
                'error': 'Compression tool not found',
                'details': str(e),
                'method': method
            }), 500
        except Exception as e:
            print(f"Unexpected error during compression: {e}")
            return jsonify({
                'error': 'Unexpected compression error',
                'details': str(e)
            }), 500
        
        if result.returncode != 0:
            print(f"Compression failed with return code: {result.returncode}")
            print(f"stdout: {result.stdout}")
            print(f"stderr: {result.stderr}")
            return jsonify({
                'error': 'Compression failed',
                'details': result.stderr,
                'return_code': result.returncode,
                'stdout': result.stdout
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
    # Get port from environment variable (for production) or use 5000
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port) 