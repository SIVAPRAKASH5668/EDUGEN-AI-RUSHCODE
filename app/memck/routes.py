from flask import Blueprint, jsonify, request, render_template
import os

from . import bp

# Initialize the MemoryCheck class
from .memck import MemoryCheck
memory_check = MemoryCheck()

@bp.route('/')
def home():
    return render_template('memck.html')
@bp.route('/upload_pdf', methods=['POST'])
def upload_pdf():
    """Route to handle PDF upload and text extraction"""
    try:
        if 'pdf' not in request.files:
            return jsonify({"error": "No PDF file uploaded"})
        
        pdf_file = request.files['pdf']
        if pdf_file.filename == '':
            return jsonify({"error": "No file selected"})
        
        text = memory_check.extract_pdf_text(pdf_file)
        return jsonify({"success": True, "text": text})
    except Exception as e:
        return jsonify({"error": str(e)})

@bp.route('/process_audio', methods=['POST'])
def process_audio():
    """Route to handle audio processing"""
    try:
        audio_data = request.json.get('audio')
        if not audio_data:
            return jsonify({"error": "No audio data received"})
        
        audio_path = memory_check.save_audio_file(audio_data)
        text = memory_check.process_audio_file(audio_path)
        
        os.remove(audio_path)  # Clean up the temporary file
        
        return jsonify({"success": True, "text": text})
    except Exception as e:
        return jsonify({"error": str(e)})

@bp.route('/compare_texts', methods=['POST'])
def compare_text_routes():
    """Route to handle text comparison"""
    try:
        data = request.json
        pdf_text = data.get('pdf_text', '')
        audio_text = data.get('audio_text', '')
        
        if not pdf_text or not audio_text:
            return jsonify({"error": "Both PDF and audio text are required"})
        
        comparison_results = memory_check.compare_texts(pdf_text, audio_text)
        return jsonify({"success": True, "results": comparison_results})
    except Exception as e:
        return jsonify({"error": str(e)})