import logging
from flask import Flask, render_template, request, flash
from transformers import pipeline
from langdetect import detect
import os

app = Flask(__name__)
app.secret_key = "supersecretkey"

# Configure logging
logging.basicConfig(filename='app.log', level=logging.INFO, 
                    format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger = logging.getLogger(__name__)

summarizer_en = pipeline("summarization", model="facebook/bart-large-cnn")
summarizer_es = pipeline("summarization", model="mrm8488/mbart-large-finetuned-opus-en-es-summarization")

def get_summarizer_for_language(lang):
    if lang == 'es':
        return summarizer_es
    return summarizer_en

def get_summary_length_config(length_choice):
    if length_choice == 'short':
        return {'max_length': 50, 'min_length': 25}
    elif length_choice == 'medium':
        return {'max_length': 130, 'min_length': 50}
    elif length_choice == 'long':
        return {'max_length': 200, 'min_length': 100}
    return {'max_length': 130, 'min_length': 50}

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/summarize', methods=['POST'])
def summarize():
    text = request.form['content']
    length_choice = request.form['length']

    if not text.strip():
        flash("Input text cannot be empty. Please enter some text to summarize.", "error")
        logger.warning("Empty input text received.")
        return render_template('index.html', summary=None, original_text=text)
    
    if len(text.split()) > 1000:
        flash("Input text is too long. Please reduce the length of the text.", "error")
        logger.warning("Input text too long.")
        return render_template('index.html', summary=None, original_text=text)

    try:
        language = detect(text)
        summarizer = get_summarizer_for_language(language)
        length_config = get_summary_length_config(length_choice)

        summary = summarizer(text, max_length=length_config['max_length'], min_length=length_config['min_length'], do_sample=False)[0]['summary_text']
        logger.info(f"Summarization successful. Language: {language}, Length: {length_choice}")
    except Exception as e:
        flash(f"Summarization error: {str(e)}", "error")
        logger.error(f"Summarization error: {str(e)}")
        return render_template('index.html', summary=None, original_text=text)

    return render_template('index.html', summary=summary, original_text=text)

if __name__ == "__main__":
    app.run(debug=True)
