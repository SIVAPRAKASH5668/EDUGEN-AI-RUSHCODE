from flask import Blueprint, render_template, request, jsonify, current_app
from werkzeug.utils import secure_filename
import os
from .rag import get_pdf_text, get_text_chunks, get_vector_store, process_question

from . import bp

@bp.route('/')
def index():
    return render_template('raggenerator.html')

@bp.route('/upload', methods=['POST'])  # Current route in rag/routes.py
def upload_file():
    try:
        if 'files[]' not in request.files:
            return jsonify({'success': False, 'error': 'No file part'}), 400
        
        files = request.files.getlist('files[]')
        if not files or files[0].filename == '':
            return jsonify({'success': False, 'error': 'No files selected'}), 400
        
        file_paths = []
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                file_paths.append(file_path)
        
        if not file_paths:
            return jsonify({'success': False, 'error': 'No valid PDF files uploaded'}), 400
        
        # Process the PDFs
        raw_text = get_pdf_text(file_paths)
        text_chunks = get_text_chunks(raw_text)
        get_vector_store(text_chunks)
        
        # Clean up uploaded files
        for file_path in file_paths:
            try:
                os.remove(file_path)
            except Exception:
                pass
        
        return jsonify({'success': True, 'message': 'Files processed successfully'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/ask', methods=['POST'])
def ask_question():
    try:
        data = request.get_json()
        if not data or 'question' not in data:
            return jsonify({'success': False, 'error': 'No question provided'}), 400
        
        question = data['question']
        response = process_question(question)
        
        return jsonify({'success': True, 'answer': response})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'pdf'}

@bp.route('/test')
def test():
    return jsonify({"status": "RAG Blueprint Working"})