import os
from dotenv import load_dotenv
import logging
from groq import Groq
import PyPDF2
from transformers import pipeline
import io

# Load environment variables
load_dotenv()

class MCQGenerator:
    def __init__(self):
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
        
        self.MCQ_TEMPLATE = {
            "english": """Generate exactly {num_questions} multiple-choice questions at {difficulty} difficulty level based on this text:

{text}

For each question use this exact format:
Q) [Question text]
A) [Option A]
B) [Option B]
C) [Option C]
D) [Option D]
Correct Answer: [Letter]
Explanation: [Brief explanation]

Make sure questions test understanding of the text. Keep options clear and distinct.""",

            "tamil": """Generate exactly {num_questions} multiple-choice questions in Tamil at {difficulty} difficulty level based on this text:

{text}

For each question use this exact format (write questions and options in Tamil):
Q) [Question text in Tamil]
A) [Option A in Tamil]
B) [Option B in Tamil]
C) [Option C in Tamil]
D) [Option D in Tamil]
Correct Answer: [Letter]
Explanation: [Brief explanation in Tamil]

Make sure questions test understanding of the text. Keep options clear and distinct."""
        }

    def extract_text_from_pdf(self, pdf_file):
        try:
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_file.read()))
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            return text.strip()
        except Exception as e:
            logging.error(f"PDF extraction error: {str(e)}")
            return None

    def summarize_text(self, text, max_length=1000):
        try:
            if len(text) > max_length:
                chunks = [text[i:i+max_length] for i in range(0, len(text), max_length)]
                summaries = []
                for chunk in chunks:
                    summary = self.summarizer(chunk, max_length=200, min_length=50, do_sample=False)
                    summaries.append(summary[0]['summary_text'])
                return ' '.join(summaries)
            return text
        except Exception as e:
            logging.error(f"Summarization error: {str(e)}")
            return text[:6000]  # Fallback to first 6000 chars if summarization fails

    def generate_mcqs(self, text, num_questions, language, difficulty):
        try:
            # Summarize text if it's too long
            summarized_text = self.summarize_text(text)
            
            # Get template based on language
            template = self.MCQ_TEMPLATE.get(language.lower(), self.MCQ_TEMPLATE['english'])
            
            # Format prompt
            prompt = template.format(
                num_questions=num_questions,
                difficulty=difficulty,
                text=summarized_text
            )

            # Generate MCQs using Groq
            response = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert quiz generator. Create clear, focused multiple-choice questions."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                model="llama-3.3-70b-versatile",
                temperature=0.3,
                max_tokens=3000,
                top_p=0.9
            )

            return response.choices[0].message.content.strip() if response.choices else None

        except Exception as e:
            logging.error(f"MCQ Generation error: {str(e)}")
            return None

    def parse_mcqs(self, mcqs):
        questions = []
        current_question = {}
        
        for line in mcqs.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            if line.startswith('Q)'):
                if current_question:
                    questions.append(current_question)
                current_question = {'question': line[2:].strip(), 'options': []}
            elif line.startswith(('A)', 'B)', 'C)', 'D)')):
                current_question['options'].append(line[2:].strip())
            elif line.startswith('Correct Answer:'):
                current_question['correct'] = line.split(':')[1].strip()
            elif line.startswith('Explanation:'):
                current_question['explanation'] = line.split(':')[1].strip()

        if current_question:
            questions.append(current_question)
            
        return questions