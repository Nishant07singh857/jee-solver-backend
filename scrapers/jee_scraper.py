import requests
from bs4 import BeautifulSoup
import fitz  # PyMuPDF
import json
import re
import os
import time

# English: This is the final, most robust scraper. It finds the latest PDF link from the NTA downloads page first.
# Hinglish: Yeh final aur sabse robust scraper hai. Yeh pehle NTA downloads page se latest PDF link dhoondta hai.

def find_latest_jee_pdf_link(base_url="https://nta.ac.in/Downloads"):
    """
    English: Visits the NTA downloads page to find the first available JEE Main Question Paper PDF link.
    Hinglish: NTA downloads page par jaakar pehla available JEE Main Question Paper PDF link dhoondta hai.
    """
    print(f"Searching for PDF links on: {base_url}")
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(base_url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # Find all links ('a' tags) on the page
        all_links = soup.find_all('a')
        for link in all_links:
            href = link.get('href', '')
            link_text = link.get_text().upper() # Get the visible text of the link and make it uppercase

            # English: New, more reliable logic. Search for keywords in the link's text.
            # Hinglish: Naya, zyada reliable logic. Link ke text mein keywords dhoondho.
            is_jee_link = "JEE" in link_text or "JOINT ENTRANCE" in link_text
            is_question_paper = "QUESTION PAPER" in link_text or "QP" in link_text
            is_pdf = href.endswith(".pdf")

            if is_jee_link and is_question_paper and is_pdf:
                # The links on the site might be relative, so we construct the full URL
                full_url = requests.compat.urljoin(base_url, href)
                print(f"Found a potential PDF link: {full_url}")
                return full_url
        
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error accessing the NTA downloads page: {e}")
        return None

def download_pdf(url, save_path="temp_paper.pdf"):
    """
    English: Downloads a PDF file from a URL.
    Hinglish: URL se ek PDF file download karta hai.
    """
    if not url:
        print("No URL provided for download.")
        return None
        
    print(f"Downloading PDF from: {url}")
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=30) # Added timeout
        response.raise_for_status()
        
        with open(save_path, 'wb') as f:
            f.write(response.content)
        print(f"Successfully downloaded PDF to {save_path}")
        return save_path
    except requests.exceptions.RequestException as e:
        print(f"Error downloading PDF: {e}")
        return None

def extract_questions_from_pdf(pdf_path):
    """
    English: Extracts questions from a downloaded PDF file.
    Hinglish: Download ki gayi PDF file se questions extract karta hai.
    """
    print(f"Extracting questions from {pdf_path}...")
    try:
        doc = fitz.open(pdf_path)
        full_text = "".join(page.get_text() for page in doc)
        doc.close()

        questions_data = []
        # This pattern is more robust and looks for "Question ID :" followed by the question text
        question_blocks = re.split(r'Question ID : \d+', full_text)[1:]

        for i, block in enumerate(question_blocks, 1):
            block_cleaned = block.strip().replace('\n', ' ')
            
            question_match = re.search(r'Options(.*?)(?=1\.)', block_cleaned, re.DOTALL)
            if not question_match:
                continue
            
            question_text = question_match.group(1).strip()
            options = re.findall(r'\d\.\s(.*?)(?=\s\d\.|$)', block_cleaned)
            
            if question_text and len(options) >= 4:
                questions_data.append({
                    "id": i,
                    "question": question_text,
                    "options": options[:4],
                    "correctAnswer": "Not Extracted",
                    "source": "NTA Official PDF"
                })

        return questions_data
    except Exception as e:
        print(f"Error extracting questions from PDF: {e}")
        return None

if __name__ == "__main__":
    # Step 1: Find the latest PDF link dynamically
    latest_pdf_url = find_latest_jee_pdf_link()
    
    if latest_pdf_url:
        PDF_FILENAME = "latest_jee_paper.pdf"
        
        # Step 2: Download the PDF from the found link
        pdf_file = download_pdf(latest_pdf_url, PDF_FILENAME)
        
        if pdf_file:
            # Step 3: Extract questions from the downloaded PDF
            scraped_data = extract_questions_from_pdf(pdf_file)
            
            if scraped_data:
                with open('scraped_nta_questions.json', 'w') as f:
                    json.dump(scraped_data, f, indent=4)
                print(f"Successfully extracted {len(scraped_data)} questions and saved to scraped_nta_questions.json")
            else:
                print("No questions could be extracted. The PDF layout might be different from the expected format.")
            
            # Step 4: Clean up the downloaded file
            os.remove(PDF_FILENAME)
    else:
        print("Could not find any JEE Main PDF link on the NTA downloads page.")
