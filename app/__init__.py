from flask import Flask
import os

def create_app():
    app = Flask(__name__)

    app.config['ALLOWED_EXTENSIONS'] = {'pdf'}  # Fix file type
    app.config['UPLOAD_FOLDER'] = os.path.join(app.instance_path, 'uploads')
    app.config['NOTES_FOLDER'] = os.path.join(app.instance_path, 'notes')
    # Wrong in create_app():
    app.config['ALLOWED_EXTENSIONS'] = {'mp4', 'avi', 'mov'}  # Video formats


    # Should be in RAG blueprint:
    ALLOWED_EXTENSIONS = {'pdf'}  # For PDF processing
    app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 10MB max upload
    
    
    # Register blueprint
    from app.video2pdf import bp as video2pdf_bp
    app.register_blueprint(video2pdf_bp, url_prefix='/video2pdf')
    
    from app.rag import bp as rag_bp
    app.register_blueprint(rag_bp, url_prefix='/rag')  # Your current setup

    from app.main_site import bp as main_bp
    app.register_blueprint(main_bp)

    # Ensure proper blueprint registration
    from app.notegen import bp as notegen_bp  # Verify import path
    app.register_blueprint(notegen_bp, url_prefix='/notegen')

    # Import blueprints
    from app.mcq import bp as mcq_bp

    app.register_blueprint(mcq_bp,url_prefix='/mcq')



    from app.memck import bp as memck_bp
    app.register_blueprint(memck_bp, url_prefix='/memck')



    return app