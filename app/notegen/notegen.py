from flask import current_app
from langchain.text_splitter import RecursiveCharacterTextSplitter
from groq import Groq
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.units import inch
from reportlab.lib.colors import blue, green, red
import os
import uuid
import json
import re
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
groq_api_key = os.getenv("GROQ_API_KEY")

# Initialize Groq client
client = Groq(api_key=groq_api_key)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'pdf'

def clean_text_for_json(text):
    """Clean text to prevent JSON parsing issues"""
    if not text:
        return ""
    
    # Replace problematic characters
    text = text.replace('\\', '\\\\')  # Escape backslashes
    text = text.replace('"', '\\"')    # Escape quotes
    text = text.replace('\n', ' ')     # Replace newlines with spaces
    text = text.replace('\r', ' ')     # Replace carriage returns
    text = text.replace('\t', ' ')     # Replace tabs
    text = re.sub(r'\s+', ' ', text)   # Normalize whitespace
    text = text.strip()
    
    # Remove or replace any non-printable characters
    text = re.sub(r'[^\x20-\x7E]', ' ', text)
    
    return text

def safe_json_parse(json_str):
    """Safely parse JSON with multiple fallback strategies"""
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        # Strategy 1: Try to fix common issues
        try:
            # Remove any text before the first {
            start = json_str.find('{')
            if start > 0:
                json_str = json_str[start:]
            
            # Remove any text after the last }
            end = json_str.rfind('}')
            if end > 0:
                json_str = json_str[:end + 1]
            
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass
        
        # Strategy 2: Try regex extraction
        try:
            # Extract JSON object using regex
            json_match = re.search(r'\{.*\}', json_str, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
        
        # Strategy 3: Return a default structure
        print(f"Failed to parse JSON: {e}")
        return {
            "topics": [{
                "id": str(uuid.uuid4()),
                "title": "Content Processing Error",
                "key_concepts": ["Unable to process content"],
                "definitions": ["Error: Could not parse AI response"],
                "examples": ["Please try again with different content"],
                "summary": "There was an error processing the content. Please try uploading different files.",
                "subtopics": []
            }]
        }

class EnhancedTopicProcessor:
    def __init__(self):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=2500,  # Reduced chunk size
            chunk_overlap=200
        )

    def process_content(self, text):
        try:
            # Clean text before processing
            cleaned_text = clean_text_for_json(text)
            
            # Split into smaller chunks for better processing
            chunks = self.text_splitter.split_text(cleaned_text)
            enhanced_topics = []
            
            # Process only first 2 chunks to avoid token limits
            for i, chunk in enumerate(chunks[:2]):
                if not chunk.strip():
                    continue
                    
                prompt = f"""Analyze the following educational content and create structured study notes. 

Text to analyze: {chunk[:1500]}

Create a JSON response with the following structure:
{{
    "topics": [
        {{
            "title": "Clear topic title",
            "key_concepts": ["concept1", "concept2", "concept3"],
            "definitions": ["term: full definition"],
            "examples": ["practical example"],
            "summary": "Brief summary of the topic"
        }}
    ]
}}

Requirements:
- Keep all text simple and avoid special characters
- Maximum 3 topics per response
- Each topic should have 3-5 key concepts
- Keep definitions and examples concise
- Ensure all JSON is properly formatted
"""
                
                try:
                    response = client.chat.completions.create(
                        messages=[{"role": "user", "content": prompt}],
                        model="llama-3.3-70b-versatile",
                        temperature=0.3,
                        response_format={"type": "json_object"},
                        max_tokens=2000
                    )
                    
                    json_str = response.choices[0].message.content
                    data = safe_json_parse(json_str)
                    
                    # Process each topic
                    if 'topics' in data:
                        for topic in data['topics']:
                            # Ensure all required fields exist
                            topic['id'] = str(uuid.uuid4())
                            topic.setdefault('key_concepts', [])
                            topic.setdefault('definitions', [])
                            topic.setdefault('examples', [])
                            topic.setdefault('summary', 'Summary not available')
                            topic.setdefault('subtopics', [])
                            
                            enhanced_topics.append(topic)
                
                except Exception as e:
                    current_app.logger.error(f"Error processing chunk {i}: {str(e)}")
                    # Add a fallback topic
                    enhanced_topics.append({
                        'id': str(uuid.uuid4()),
                        'title': f'Content Section {i + 1}',
                        'key_concepts': ['Content extracted from uploaded files'],
                        'definitions': ['Processing error occurred'],
                        'examples': ['Please try re-uploading the files'],
                        'summary': 'There was an error processing this section.',
                        'subtopics': []
                    })
            
            return enhanced_topics[:5]  # Return max 5 topics

        except Exception as e:
            current_app.logger.error(f"Content processing error: {str(e)}")
            raise RuntimeError(f"Processing error: {str(e)}")

    def generate_mcq_test(self, text, difficulty="medium", num_questions=10):
        """Generate MCQ test based on the processed content"""
        try:
            # Clean and limit text
            cleaned_text = clean_text_for_json(text)[:2000]  # Limit text length
            
            difficulty_map = {
                "easy": "basic recall questions focusing on definitions and simple facts",
                "medium": "application questions requiring understanding and basic analysis", 
                "hard": "complex analysis questions requiring synthesis of multiple concepts"
            }
            
            difficulty_instruction = difficulty_map.get(difficulty, difficulty_map["medium"])
            
            prompt = f"""Create {min(num_questions, 15)} multiple choice questions based on this content.

Content: {cleaned_text}

Create {difficulty_instruction}.

Return JSON in this exact format:
{{
    "test_info": {{
        "title": "Practice Test",
        "difficulty": "{difficulty}",
        "total_questions": {min(num_questions, 15)},
        "time_limit": 30
    }},
    "questions": [
        {{
            "id": 1,
            "question": "Question text?",
            "options": {{
                "A": "Option A text",
                "B": "Option B text",
                "C": "Option C text",
                "D": "Option D text"
            }},
            "correct_answer": "A",
            "explanation": "Why A is correct",
            "difficulty": "{difficulty}",
            "topic": "Topic name"
        }}
    ]
}}

Requirements:
- Keep questions and options concise
- Avoid special characters and complex formatting
- Each question must have exactly 4 options (A, B, C, D)
- Only one correct answer per question
- Include clear explanations
"""
            
            response = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.3-70b-versatile",
                temperature=0.3,
                response_format={"type": "json_object"},
                max_tokens=3000
            )
            
            json_str = response.choices[0].message.content
            mcq_data = safe_json_parse(json_str)
            
            # Validate and fix the structure
            if 'test_info' not in mcq_data:
                mcq_data['test_info'] = {
                    'title': 'Practice Test',
                    'difficulty': difficulty,
                    'total_questions': num_questions,
                    'time_limit': 30
                }
            
            if 'questions' not in mcq_data:
                mcq_data['questions'] = []
            
            # Ensure questions have proper structure
            valid_questions = []
            for i, q in enumerate(mcq_data.get('questions', [])):
                if not isinstance(q, dict):
                    continue
                    
                question = {
                    'id': i + 1,
                    'question': q.get('question', f'Question {i + 1}'),
                    'options': q.get('options', {'A': 'Option A', 'B': 'Option B', 'C': 'Option C', 'D': 'Option D'}),
                    'correct_answer': q.get('correct_answer', 'A'),
                    'explanation': q.get('explanation', 'Explanation not available'),
                    'difficulty': difficulty,
                    'topic': q.get('topic', 'General')
                }
                valid_questions.append(question)
            
            mcq_data['questions'] = valid_questions
            mcq_data['test_info']['test_id'] = str(uuid.uuid4())
            mcq_data['test_info']['total_questions'] = len(valid_questions)
            
            return mcq_data
            
        except Exception as e:
            current_app.logger.error(f"MCQ generation error: {str(e)}")
            raise RuntimeError(f"MCQ generation error: {str(e)}")

class EnhancedPDFGenerator:
    @staticmethod
    def create_pdf(topic):
        filename = f"notes_{topic['id']}.pdf"
        filepath = os.path.join(current_app.config['NOTES_FOLDER'], filename)
        
        doc = SimpleDocTemplate(filepath, pagesize=letter)
        styles = getSampleStyleSheet()
        elements = []
        
        # Custom Styles
        title_style = ParagraphStyle(
            'Title',
            parent=styles['Heading1'],
            fontSize=22,
            leading=24,
            spaceAfter=14,
            textColor=blue
        )
        
        heading_style = ParagraphStyle(
            'Heading',
            parent=styles['Heading2'],
            fontSize=16,
            textColor=blue,
            spaceAfter=8
        )
        
        bullet_style = ParagraphStyle(
            'Bullet',
            parent=styles['BodyText'],
            fontSize=12,
            leading=14,
            leftIndent=10,
            spaceAfter=6
        )
        
        # Clean and add content
        title = clean_text_for_json(topic.get('title', 'Study Notes'))
        elements.append(Paragraph(title, title_style))
        
        # Key Concepts
        key_concepts = topic.get('key_concepts', [])
        if key_concepts:
            elements.append(Paragraph("Key Concepts:", heading_style))
            for concept in key_concepts:
                clean_concept = clean_text_for_json(str(concept))
                elements.append(Paragraph(f"• {clean_concept}", bullet_style))
            elements.append(Spacer(1, 16))
        
        # Definitions
        definitions = topic.get('definitions', [])
        if definitions:
            elements.append(Paragraph("Important Definitions:", heading_style))
            for definition in definitions:
                clean_def = clean_text_for_json(str(definition))
                elements.append(Paragraph(f"‣ {clean_def}", bullet_style))
            elements.append(Spacer(1, 16))
        
        # Examples
        examples = topic.get('examples', [])
        if examples:
            elements.append(Paragraph("Examples:", heading_style))
            for example in examples:
                clean_example = clean_text_for_json(str(example))
                elements.append(Paragraph(f"⁃ {clean_example}", bullet_style))
            elements.append(Spacer(1, 16))
        
        # Summary
        summary = topic.get('summary', 'No summary available')
        elements.append(Paragraph("Summary:", heading_style))
        clean_summary = clean_text_for_json(str(summary))
        elements.append(Paragraph(clean_summary, bullet_style))
        
        try:
            doc.build(elements)
        except Exception as e:
            current_app.logger.error(f"PDF generation error: {str(e)}")
            # Create a simple fallback PDF
            elements = [Paragraph("Study Notes", title_style),
                       Paragraph("Error generating detailed notes. Please try again.", bullet_style)]
            doc.build(elements)
        
        return filename

    @staticmethod
    def create_mcq_pdf(mcq_data):
        """Generate PDF for MCQ test with answers and results"""
        test_id = mcq_data['test_info']['test_id']
        filename = f"mcq_test_{test_id}.pdf"
        filepath = os.path.join(current_app.config['NOTES_FOLDER'], filename)
        
        doc = SimpleDocTemplate(filepath, pagesize=letter)
        styles = getSampleStyleSheet()
        elements = []
        
        # Custom Styles
        title_style = ParagraphStyle(
            'Title',
            parent=styles['Heading1'],
            fontSize=20,
            leading=22,
            spaceAfter=12,
            textColor=blue
        )
        
        question_style = ParagraphStyle(
            'Question',
            parent=styles['BodyText'],
            fontSize=14,
            leading=16,
            spaceAfter=8,
            fontName='Helvetica-Bold'
        )
        
        option_style = ParagraphStyle(
            'Option',
            parent=styles['BodyText'],
            fontSize=12,
            leading=14,
            leftIndent=20,
            spaceAfter=4
        )
        
        # Add title and test info
        test_title = clean_text_for_json(mcq_data['test_info'].get('title', 'Practice Test'))
        elements.append(Paragraph(test_title, title_style))
        elements.append(Paragraph(f"Difficulty: {mcq_data['test_info']['difficulty'].title()}", styles['BodyText']))
        elements.append(Paragraph(f"Total Questions: {mcq_data['test_info']['total_questions']}", styles['BodyText']))
        elements.append(Spacer(1, 24))
        
        # Get user answers if provided
        user_answers = mcq_data.get('user_answers', {})
        
        # Add questions
        elements.append(Paragraph("Questions and Answers", title_style))
        
        for i, question in enumerate(mcq_data.get('questions', []), 1):
            try:
                clean_question = clean_text_for_json(question.get('question', f'Question {i}'))
                elements.append(Paragraph(f"Q{i}. {clean_question}", question_style))
                
                user_answer = user_answers.get(str(i-1)) if user_answers else None
                correct_answer = question.get('correct_answer', 'A')
                
                options = question.get('options', {})
                for option_key, option_text in options.items():
                    clean_option = clean_text_for_json(str(option_text))
                    option_prefix = f"{option_key}. {clean_option}"
                    
                    if option_key == correct_answer:
                        option_prefix += " ✓ (Correct)"
                    elif option_key == user_answer and user_answer != correct_answer:
                        option_prefix += " ✗ (Your answer)"
                    
                    elements.append(Paragraph(option_prefix, option_style))
                
                # Add explanation
                explanation = question.get('explanation', 'No explanation available')
                clean_explanation = clean_text_for_json(str(explanation))
                elements.append(Paragraph(f"Explanation: {clean_explanation}", option_style))
                elements.append(Spacer(1, 16))
                
            except Exception as e:
                current_app.logger.error(f"Error adding question {i} to PDF: {str(e)}")
                continue
        
        try:
            doc.build(elements)
        except Exception as e:
            current_app.logger.error(f"MCQ PDF generation error: {str(e)}")
            # Create a simple fallback PDF
            elements = [Paragraph("MCQ Test Results", title_style),
                       Paragraph("Error generating detailed test results. Please try again.", styles['BodyText'])]
            doc.build(elements)
        
        return filename