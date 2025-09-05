from flask import render_template, request, send_file, current_app, jsonify, url_for
from werkzeug.utils import secure_filename
import os
import uuid
from .video_processor import VideoProcessor
from .pdf_generator import PDFGenerator, SlideProcessor
from . import bp

# Track generated PDFs with their IDs
pdf_cache = {}

from flask import render_template, request, send_file, current_app, jsonify
from werkzeug.utils import secure_filename
import os
from .video_processor import VideoProcessor
from .pdf_generator import PDFGenerator, SlideProcessor
from . import bp
import logging

@bp.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST' and 'video' in request.files:
        video_file = request.files['video']
        if video_file and video_file.filename:
            try:
                # Save uploaded video
                filename = secure_filename(video_file.filename)
                upload_folder = current_app.config['UPLOAD_FOLDER']
                
                # Make sure upload folder exists
                os.makedirs(upload_folder, exist_ok=True)
                
                # Use os.path.join and normalize path with os.path.abspath
                video_path = os.path.abspath(os.path.join(upload_folder, filename))
                video_file.save(video_path)
                
                # Process video
                processor = VideoProcessor(video_path)
                slides_folder = processor.process_video()
                
                # Generate PDF
                pdf_filename = f"{os.path.splitext(filename)[0]}.pdf"
                pdf_output = os.path.join(slides_folder, "output.pdf")
                
                # Make sure we're using the actual path returned by the slide processor
                slide_processor = SlideProcessor(slides_folder, pdf_output)
                pdf_path = slide_processor.process_slide_images()
                
                # Convert to absolute path and normalize slashes
                pdf_path = os.path.abspath(pdf_path)
                current_app.logger.info(f"Generated PDF path (normalized): {pdf_path}")
                
                # Check if file exists before sending
                if not os.path.exists(pdf_path):
                    current_app.logger.error(f"PDF file not found at: {pdf_path}")
                    return jsonify({"error": "PDF generation failed - file not found"}), 500
                
                # Return the PDF file
                return send_file(
                    pdf_path,
                    mimetype='application/pdf',
                    as_attachment=False  # Show in browser
                )
                
            except Exception as e:
                import traceback
                current_app.logger.error(f"Error processing video: {str(e)}")
                current_app.logger.error(traceback.format_exc())
                return jsonify({"error": f"Error processing video: {str(e)}"}), 500
                
    return render_template('video2pdf.html')

@bp.route('/download/<conversion_id>', methods=['GET'])
def download_pdf(conversion_id):
    """Endpoint to download a previously generated PDF"""
    if conversion_id in pdf_cache:
        pdf_info = pdf_cache[conversion_id]
        return send_file(
            pdf_info['path'],
            mimetype='application/pdf',
            as_attachment=True,  # Force download
            download_name=pdf_info['filename']
        )
    else:
        return jsonify({'error': 'PDF not found'}), 404

# Optional: Clean up temporary files periodically
@bp.route('/cleanup', methods=['POST'])
def cleanup():
    """Admin endpoint to clean up old files"""
    # Add authentication here
    try:
        # Delete files older than X days
        # Implementation depends on your needs
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500