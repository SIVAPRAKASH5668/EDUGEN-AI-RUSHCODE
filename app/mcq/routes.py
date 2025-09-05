from flask import render_template, request, jsonify
import logging
from . import bp
from .mcq_generator import MCQGenerator

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize MCQ Generator
mcq_generator = MCQGenerator()

@bp.route('/')
def home():
    return render_template('mcq.html')

@bp.route('/generate', methods=['POST'])
def generate():
    try:
        # File validation
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'Please upload a PDF file'}), 400
            
        file = request.files['file']
        if not file or file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400
        if not file.filename.lower().endswith('.pdf'):
            return jsonify({'success': False, 'error': 'Invalid file format. Please upload a PDF.'}), 400

        # Extract text
        text = mcq_generator.extract_text_from_pdf(file)
        if not text:
            return jsonify({
                'success': False,
                'error': 'Failed to extract text from PDF. Please ensure the PDF contains selectable text.'
            }), 400

        # Get and validate form data
        num_questions = request.form.get('num_questions', '5')
        try:
            num_questions = int(num_questions)
            if not 1 <= num_questions <= 10:
                raise ValueError
        except ValueError:
            return jsonify({'success': False, 'error': 'Number of questions must be between 1 and 10'}), 400

        difficulty = request.form.get('difficulty', 'Medium')
        language = request.form.get('language', 'english')

        # Generate questions
        raw_mcqs = mcq_generator.generate_mcqs(text, num_questions, language, difficulty)
        if not raw_mcqs:
            return jsonify({'success': False, 'error': 'Failed to generate questions. Please try again.'}), 500

        # Parse questions
        questions = mcq_generator.parse_mcqs(raw_mcqs)
        if not questions:
            return jsonify({'success': False, 'error': 'Failed to parse generated questions'}), 500

        return jsonify({'success': True, 'questions': questions})

    except Exception as e:
        logging.error(f"Error generating MCQs: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': 'An unexpected error occurred. Please try again.'}), 500