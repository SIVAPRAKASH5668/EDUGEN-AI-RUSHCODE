from flask import Blueprint, render_template, request, jsonify, send_file, current_app
from werkzeug.utils import secure_filename
import os
from PyPDF2 import PdfReader
from .notegen import EnhancedTopicProcessor, EnhancedPDFGenerator, allowed_file
import time

# Create blueprint
from . import bp

@bp.route('/')
def home():
    return render_template('notesprovider.html')

@bp.route('/upload', methods=['POST'])
def handle_upload():
    if 'files[]' not in request.files:
        return jsonify({'error': 'No files selected'}), 400
    
    files = request.files.getlist('files[]')
    if not files:
        return jsonify({'error': 'No valid files'}), 400

    try:
        # Process files
        saved_files = []
        all_text = ""  # Store all text for MCQ generation
        
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                file.save(path)
                saved_files.append(path)
        
        # Extract text from all files
        for path in saved_files:
            try:
                reader = PdfReader(path)
                file_text = ""
                for page in reader.pages:
                    file_text += page.extract_text() + "\n"
                all_text += file_text + "\n\n"
            except Exception as e:
                current_app.logger.error(f"Error reading PDF {path}: {str(e)}")
                continue
        
        if not all_text.strip():
            return jsonify({'error': 'No text could be extracted from the uploaded files'}), 400
        
        # Process content
        processor = EnhancedTopicProcessor()
        topics = processor.process_content(all_text)
        
        if not topics:
            return jsonify({'error': 'No topics could be generated from the content'}), 400
        
        # Generate PDFs for each topic
        for topic in topics:
            try:
                topic['pdf'] = EnhancedPDFGenerator.create_pdf(topic)
            except Exception as e:
                current_app.logger.error(f"Error generating PDF for topic: {str(e)}")
                topic['pdf'] = None
        
        # Cleanup uploaded files
        for path in saved_files:
            try:
                os.remove(path)
            except:
                pass
        
        return jsonify({
            'success': True, 
            'topics': topics,
            'original_text': all_text  # Include original text for MCQ generation
        })
        
    except Exception as e:
        current_app.logger.error(f"Upload processing error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/generate_mcq', methods=['POST'])
def generate_mcq():
    """Generate MCQ test from processed content"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        text = data.get('text', '')
        difficulty = data.get('difficulty', 'medium')
        num_questions = data.get('num_questions', 10)

        if not text.strip():
            return jsonify({'success': False, 'error': 'No content available for MCQ generation'}), 400

        # Validate parameters
        if difficulty not in ['easy', 'medium', 'hard']:
            difficulty = 'medium'
        
        try:
            num_questions = int(num_questions)
            if num_questions < 1 or num_questions > 50:  # Reasonable limits
                num_questions = 10
        except (ValueError, TypeError):
            num_questions = 10

        # Generate MCQ test
        processor = EnhancedTopicProcessor()
        mcq_data = processor.generate_mcq_test(text, difficulty, num_questions)
        
        return jsonify({
            'success': True,
            'mcq_data': mcq_data
        })

    except Exception as e:
        current_app.logger.error(f"MCQ generation error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/download_mcq_pdf', methods=['POST'])
def download_mcq_pdf():
    """Generate and download MCQ test PDF"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        mcq_data = data.get('mcq_data')
        user_answers = data.get('user_answers', {})

        if not mcq_data:
            return jsonify({'error': 'No MCQ data provided'}), 400

        # Add user answers to MCQ data for PDF generation
        mcq_data['user_answers'] = user_answers

        # Generate PDF
        pdf_filename = EnhancedPDFGenerator.create_mcq_pdf(mcq_data)
        filepath = os.path.join(current_app.config['NOTES_FOLDER'], pdf_filename)

        if os.path.exists(filepath):
            return send_file(
                filepath, 
                as_attachment=True, 
                download_name=f"MCQ_Test_{mcq_data['test_info']['difficulty']}.pdf",
                mimetype='application/pdf'
            )
        else:
            return jsonify({'error': 'PDF generation failed'}), 500

    except Exception as e:
        current_app.logger.error(f"MCQ PDF download error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/save_test_results', methods=['POST'])
def save_test_results():
    """Save test results for future reference"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        test_id = data.get('test_id')
        user_answers = data.get('user_answers', {})
        score = data.get('score', 0)
        time_taken = data.get('time_taken', 0)
        
        # Here you could save to database or file
        # For now, we'll just return success with the data
        results = {
            'test_id': test_id,
            'score': score,
            'time_taken': time_taken,
            'total_questions': len(user_answers),
            'timestamp': int(time.time())
        }
        
        # Log the results for now (you can extend this to save to database)
        current_app.logger.info(f"Test results saved: {results}")
        
        return jsonify({
            'success': True,
            'message': 'Test results saved successfully',
            'results': results
        })
        
    except Exception as e:
        current_app.logger.error(f"Save test results error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/get_test_history')
def get_test_history():
    """Get user's test history"""
    try:
        # This would typically fetch from database
        # For demo, return empty history
        # You can extend this to fetch from your database
        return jsonify({
            'success': True,
            'history': []  # Replace with actual database query
        })
    except Exception as e:
        current_app.logger.error(f"Get test history error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

# Keep your existing download route
@bp.route('/download/<filename>')
def serve_pdf(filename):
    try:
        # Add verification and logging
        file_path = os.path.join(current_app.config['NOTES_FOLDER'], filename)
        if not os.path.exists(file_path):
            current_app.logger.error(f"File not found: {file_path}")
            return jsonify({'error': 'File not found'}), 404
        
        return send_file(
            file_path,
            as_attachment=True,
            download_name=f"StudyNotes_{filename}",
            mimetype='application/pdf'
        )
    except Exception as e:
        current_app.logger.error(f"Download error: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Error handlers for the blueprint
@bp.errorhandler(413)
def too_large(e):
    return jsonify({'success': False, 'error': 'File too large. Maximum size exceeded.'}), 413

@bp.errorhandler(500)
def internal_error(e):
    current_app.logger.error(f"Internal server error: {str(e)}")
    return jsonify({'success': False, 'error': 'Internal server error occurred.'}), 500