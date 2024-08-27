from flask import Flask, render_template, request, flash
from transformers import pipeline
from transformers.pipelines import PipelineException
from langdetect import detect

app = Flask(__name__)
app.secret_key = "supersecretkey"  # Required for flashing messages

# Load different summarization models for different languages
summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
summarizer_es = pipeline("summarization", model="mrm8488/mbart-large-finetuned-opus-en-es-summarization")
# You can add more models for other languages here

def get_summarizer_for_language(lang):
    if lang == 'es':
        return summarizer_es
    # Add more conditions for other languages
    return summarizer_en  # Default to English model

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/summarize', methods=['POST'])
def summarize():
    text = request.form['content']

    # Error handling for empty input
    if not text.strip():
        flash("Input text cannot be empty. Please enter some text to summarize.", "error")
        return render_template('index.html', summary=None, original_text=text)
    
    # Error handling for overly long text input
    if len(text.split()) > 1000:  # Limiting to 1000 words for the summarizer
        flash("Input text is too long. Please reduce the length of the text.", "error")
        return render_template('index.html', summary=None, original_text=text)

    try:
        # Detect language
        language = detect(text)
        summarizer = get_summarizer_for_language(language)

        # Perform summarization
        summary = summarizer(text, max_length=130, min_length=30, do_sample=False)[0]['summary_text']
    except Exception as e:
        flash(f"Summarization error: {str(e)}", "error")
        return render_template('index.html', summary=None, original_text=text)

    return render_template('index.html', summary=summary, original_text=text)

if __name__ == "__main__":
    app.run(debug=True)
