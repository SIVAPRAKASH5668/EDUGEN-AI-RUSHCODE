import speech_recognition as sr
import PyPDF2
from transformers import pipeline
import base64
import logging
import os
import time
import wave
import numpy as np
from difflib import SequenceMatcher
from werkzeug.utils import secure_filename

class MemoryCheck:
    def __init__(self, upload_folder='uploads'):
        self.upload_folder = upload_folder
        self._setup_upload_folder()
        self._setup_logging()
        
    def _setup_upload_folder(self):
        """Initialize upload folder if it doesn't exist"""
        if not os.path.exists(self.upload_folder):
            os.makedirs(self.upload_folder)
            
    def _setup_logging(self):
        """Configure logging"""
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    def save_audio_file(self, audio_data):
        """Saves the audio data as a WAV file in the upload folder."""
        try:
            filename = secure_filename(f"audio_{str(int(time.time()))}.wav")
            filepath = os.path.join(self.upload_folder, filename)
            
            # Decode the base64 audio data
            audio_data = audio_data.split(',')[1]
            audio_binary = base64.b64decode(audio_data)

            # Convert the binary audio data to numpy array
            audio_np = np.frombuffer(audio_binary, dtype=np.float32)

            # Create WAV file with proper format
            with wave.open(filepath, 'wb') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(44100)
                audio_int16 = (audio_np * 32767).astype(np.int16)
                wav_file.writeframes(audio_int16.tobytes())

            return filepath
        except Exception as e:
            self.logger.error(f"Audio saving error: {str(e)}")
            raise

    def process_audio_file(self, filepath):
        """Process the audio file and return the extracted text."""
        try:
            recognizer = sr.Recognizer()
            with sr.AudioFile(filepath) as source:
                recognizer.adjust_for_ambient_noise(source)
                audio = recognizer.record(source)
            text = recognizer.recognize_google(audio)
            return text
        except Exception as e:
            self.logger.error(f"Speech recognition error: {str(e)}")
            raise

    def extract_pdf_text(self, pdf_file):
        """Extract and summarize text from PDF."""
        try:
            filename = secure_filename(pdf_file.filename)
            filepath = os.path.join(self.upload_folder, filename)
            pdf_file.save(filepath)

            with open(filepath, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text()

            os.remove(filepath)  # Clean up
            
            summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
            max_chunk_length = 1024
            chunks = [text[i:i+max_chunk_length] for i in range(0, len(text), max_chunk_length)]
            
            summarized_chunks = []
            for chunk in chunks:
                if len(chunk.split()) > 50:
                    summary = summarizer(chunk, max_length=130, min_length=30, do_sample=False)
                    summarized_chunks.append(summary[0]['summary_text'])
                else:
                    summarized_chunks.append(chunk)
            
            return " ".join(summarized_chunks)
        except Exception as e:
            self.logger.error(f"PDF processing error: {str(e)}")
            raise

    def compare_texts(self, pdf_text, audio_text):
        """Compare PDF text with audio text and return analysis."""
        try:
            # Convert texts to lowercase for better comparison
            pdf_text = pdf_text.lower()
            audio_text = audio_text.lower()

            # Calculate similarity ratio
            similarity = SequenceMatcher(None, pdf_text, audio_text).ratio()
            
            # Calculate grade based on similarity
            grade = self._calculate_grade(similarity)
            
            # Find missing words
            pdf_words = set(pdf_text.split())
            audio_words = set(audio_text.split())
            missing_words = pdf_words - audio_words
            
            # Find extra words
            extra_words = audio_words - pdf_words
            
            return {
                "similarity_percentage": round(similarity * 100, 2),
                "grade": grade,
                "missing_words": list(missing_words)[:10],  # Limit to top 10 missing words
                "extra_words": list(extra_words)[:10],      # Limit to top 10 extra words
                "word_count_difference": abs(len(pdf_words) - len(audio_words))
            }
        except Exception as e:
            self.logger.error(f"Text comparison error: {str(e)}")
            raise

    def _calculate_grade(self, similarity):
        """Calculate grade based on similarity ratio."""
        if similarity >= 0.9:
            return "A"
        elif similarity >= 0.8:
            return "B"
        elif similarity >= 0.7:
            return "C"
        elif similarity >= 0.6:
            return "D"
        else:
            return "F"