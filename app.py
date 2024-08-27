import logging
from flask import Flask, render_template, request, flash, redirect, url_for
from transformers import pipeline
from langdetect import detect
import os
from PyPDF2 import PdfReader
from docx import Document
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

app = Flask(__name__)
app.secret_key = "supersecretkey"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///summarizer.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

logging.basicConfig(filename='app.log', level=logging.INFO, 
                    format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger = logging.getLogger(__name__)

summarizer_en = pipeline("summarization", model="facebook/bart-large-cnn")
summarizer_es = pipeline("summarization", model="mrm8488/mbart-large-finetuned-opus-en-es-summarization")

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Database Models
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)

class Summary(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    original_text = db.Column(db.Text, nullable=False)
    summary_text = db.Column(db.Text, nullable=False)
    language = db.Column(db.String(10), nullable=False)
    length_choice = db.Column(db.String(10), nullable=False)

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

def extract_text_from_pdf(file):
    reader = PdfReader(file)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text

def extract_text_from_docx(file):
    doc = Document(file)
    text = ""
    for para in doc.paragraphs:
        text += para.text + "\n"
    return text

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/summarize', methods=['POST'])
@login_required
def summarize():
    text = request.form['content']
    file = request.files['file']
    length_choice = request.form['length']

    if file:
        try:
            if file.filename.endswith('.pdf'):
                text = extract_text_from_pdf(file)
            elif file.filename.endswith('.docx'):
                text = extract_text_from_docx(file)
            else:
                flash("Unsupported file format. Please upload a PDF or Word document.", "error")
                logger.warning(f"Unsupported file format: {file.filename}")
                return render_template('index.html', summary=None, original_text=text)
        except Exception as e:
            flash(f"Error processing file: {str(e)}", "error")
            logger.error(f"Error processing file: {str(e)}")
            return render_template('index.html', summary=None, original_text=text)

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

        # Save to database
        new_summary = Summary(user_id=current_user.id, original_text=text, summary_text=summary, language=language, length_choice=length_choice)
        db.session.add(new_summary)
        db.session.commit()

        logger.info(f"Summarization successful. Language: {language}, Length: {length_choice}")
    except Exception as e:
        flash(f"Summarization error: {str(e)}", "error")
        logger.error(f"Summarization error: {str(e)}")
        return render_template('index.html', summary=None, original_text=text)

    return render_template('index.html', summary=summary, original_text=text)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'error')
            return redirect(url_for('register'))

        new_user = User(username=username, password=password)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful. Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username, password=password).first()
        if user:
            login_user(user)
            flash('Login successful!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid credentials', 'error')
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

@app.route('/history')
@login_required
def history():
    summaries = Summary.query.filter_by(user_id=current_user.id).all()
    return render_template('history.html', summaries=summaries)

if __name__ == "__main__":
    db.create_all()  # Creates the database tables
    app.run(debug=True)
