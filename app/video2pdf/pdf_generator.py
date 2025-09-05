import os
import re
import groq
import pytesseract
import cv2
from PIL import Image
from fpdf import FPDF
from dotenv import load_dotenv
from ultralytics import YOLO


class PDFGenerator(FPDF):
    def __init__(self):
        super().__init__()
        # Enable Unicode support
        self.add_font('DejaVu', '', 'app/fonts/dejavu-sans/DejaVuSans.ttf', uni=True)
        self.set_font('DejaVu', '', 12)
        self.set_auto_page_break(auto=True, margin=15)

    def header(self):
        pass

    def footer(self):
        pass

    def add_slide(self, text, image_path):
        """Add a slide to the PDF."""
        self.add_page()

        # Add text to PDF
        self.set_font('DejaVu', '', 12)
        lines = text.split('\n')
        for line in lines:
            self.multi_cell(0, 10, line.encode('latin-1', 'replace').decode('latin-1'))

        # Add image
        self.ln(10)
        try:
            self.image(image_path, x=10, y=self.get_y(), w=180)
        except Exception as e:
            print(f"Warning: Could not add image to PDF: {e}")


class SlideProcessor:
    def __init__(self, slides_folder, output_style="folders"):
        self.slides_folder = slides_folder
        self.output_style = output_style
        self.output_folder = os.path.join(os.path.dirname(slides_folder), 'processed_slides')
        os.makedirs(self.output_folder, exist_ok=True)

        # Load environment variables
        load_dotenv()
        self.GROQ_API_KEY = os.getenv("GROQ_API_KEY")

        # Setup Groq API client
        self.client = groq.Groq(api_key=self.GROQ_API_KEY)

        # Initialize YOLO model
        self.model = YOLO("app/model/best.pt")

        # Setup Tesseract for OCR
        pytesseract.pytesseract.tesseract_cmd = r"/usr/bin/tesseract"

    def extract_slide_number(self, filename):
        """Extract slide number from filename."""
        numbers = re.findall(r'\d+', filename)
        return int(numbers[0]) if numbers else 0

    def yolo_and_ocr(self, image_path):
        """Perform object detection using YOLO and text extraction using Tesseract OCR."""
        # Perform object detection
        result = self.model(image_path)
        
        # Get the annotated image
        result_image = result[0].plot()
        
        # Convert the detected image to RGB for OCR
        image_rgb = cv2.cvtColor(result_image, cv2.COLOR_BGR2RGB)
        
        # Perform OCR to extract text
        text = pytesseract.image_to_string(image_rgb)

        # Convert to PIL Image
        pil_image = Image.fromarray(result_image)

        return pil_image, text

    def correct_text_with_groq(self, text):
        """Send the extracted text to Groq API to organize and correct the content."""
        completion = self.client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "Organize and correct the content."},
                {"role": "user", "content": text}
            ],
            temperature=0.7,
            top_p=1,
            stream=False
        )

        return completion.choices[0].message.content

    import os
    from PIL import Image

    def process_slide_images(self):
        """
        Process slide images from a given folder to extract text and objects, save results in folders, and compile a PDF.
        """
        # 🔒 Step 1: Validate source folder
        if not os.path.exists(self.slides_folder):
            raise FileNotFoundError(f"Slides folder does not exist: {self.slides_folder}")

        # 📁 Step 2: Ensure output folder exists
        os.makedirs(self.output_folder, exist_ok=True)

        # 🖼️ Step 3: List and sort slide image files
        slide_files = [f for f in os.listdir(self.slides_folder) if f.lower().endswith('.jpg')]
        slide_files.sort(key=self.extract_slide_number)

        # 📄 Step 4: Create a PDF generator
        pdf = PDFGenerator()

        # 🔁 Step 5: Loop through each slide and process
        for slide_file in slide_files:
            slide_path = os.path.join(self.slides_folder, slide_file)
            slide_number = self.extract_slide_number(slide_file)

            print(f"Processing slide {slide_number} ({slide_file})...")

            # Run detection + OCR
            result_image, text = self.yolo_and_ocr(slide_path)

            # Determine output paths
            if self.output_style == "folders":
                slide_folder = os.path.join(self.output_folder, f"slide{slide_number}")
                os.makedirs(slide_folder, exist_ok=True)

                result_image_path = os.path.join(slide_folder, "diagram.jpg")
                text_path = os.path.join(slide_folder, "text.txt")
                original_copy_path = os.path.join(slide_folder, "original.jpg")
            else:
                result_image_path = os.path.join(self.output_folder, f"slide{slide_number}-diagram.jpg")
                text_path = os.path.join(self.output_folder, f"slide{slide_number}-text.txt")
                original_copy_path = os.path.join(self.output_folder, f"slide{slide_number}-original.jpg")

            # Save original slide image
            Image.open(slide_path).save(original_copy_path)

            # Correct text using Groq
            corrected_text = self.correct_text_with_groq(text)

            # Save corrected text
            with open(text_path, "w", encoding='utf-8') as text_file:
                text_file.write(corrected_text)

            # Save processed diagram image and add to PDF
            result_image.save(result_image_path)
            pdf.add_slide(corrected_text, result_image_path)

            print(f"Saved results for slide {slide_number}")

        # 📥 Step 6: Save final PDF
        try:
            # Ensure the full directory path for the PDF exists
            os.makedirs(self.output_folder, exist_ok=True)

            pdf_output = os.path.join(self.output_folder, 'output.pdf')
            pdf.output(pdf_output, 'F')
            print(f"✅ PDF saved successfully at: {pdf_output}")
            
        except Exception as e:
            print(f"❌ Error saving PDF: {e}")
            pdf_output = None

        return pdf_output
