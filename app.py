import logging
from flask import Flask, render_template, request, flash, redirect, url_for
from transformers import pipeline
from langdetect import detect
import os
from PyPDF2 import PdfReader
from docx import Document
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'supersecretkey')  # Replace with a real secret key
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///summarizer.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Email configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'  # Replace with your email provider's SMTP server
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_USERNAME')

db = SQLAlchemy(app)
mail = Mail(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
s = URLSafeTimedSerializer(app.secret_key)

# Logging configuration
logging.basicConfig(filename='app.log', level=logging.INFO, 
                    format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger = logging.getLogger(__name__)

# Summarization pipelines
summarizer_en = pipeline("summarization", model="facebook/bart-large-cnn")
summarizer_es = pipeline("summarization", model="mrm8488/mbart-large-finetuned-opus-en-es-summarization")

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Database models
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    confirmed = db.Column(db.Boolean, default=False)

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)

class Summary(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    original_text = db.Column(db.Text, nullable=False)
    summary_text = db.Column(db.Text, nullable=False)
    language = db.Column(db.String(10), nullable=False)
    length_choice = db.Column(db.String(10), nullable=False)

# Utility functions
def send_verification_email(user_email, token):
    msg = Message('Confirm your Email', recipients=[user_email])
    link = url_for('confirm_email', token=token, _external=True)
    msg.body = f'Your link is {link}'
    mail.send(msg)

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

# Routes
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'error')
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'error')
            return redirect(url_for('register'))

        new_user = User(username=username, email=email)
        new_user.set_password(password)  # Hashing the password before storing
        db.session.add(new_user)
        db.session.commit()

        token = s.dumps(email, salt='email-confirm')
        send_verification_email(email, token)

        flash('Registration successful. Please check your email to confirm your account.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/confirm_email/<token>')
def confirm_email(token):
    try:
        email = s.loads(token, salt='email-confirm', max_age=3600)
    except SignatureExpired:
        return '<h1>The token is expired!</h1>'
    
    user = User.query.filter_by(email=email).first_or_404()
    if user.confirmed:
        flash('Account already confirmed. Please login.', 'info')
        return redirect(url_for('login'))
    else:
        user.confirmed = True
        db.session.add(user)
        db.session.commit()
        flash('You have confirmed your account. Thanks!', 'success')
        return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):  # Verifying the password
            if user.confirmed:
                login_user(user)
                flash('Login successful!', 'success')
                return redirect(url_for('home'))
            else:
                flash('Please confirm your email first.', 'warning')
                return redirect(url_for('login'))
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
    page = request.args.get('page', 1, type=int)
    summaries = Summary.query.filter_by(user_id=current_user.id).paginate(page=page, per_page=5)
    return render_template('history.html', summaries=summaries)

@app.route('/edit_summary/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_summary(id):
    summary = Summary.query.get_or_404(id)
    if summary.user_id != current_user.id:
        flash('Unauthorized action.', 'error')
        return redirect(url_for('history'))

    if request.method == 'POST':
        summary.original_text = request.form['original_text']
        summary.summary_text = request.form['summary_text']
        db.session.commit()
        flash('Summary updated successfully.', 'success')
        return redirect(url_for('history'))

    return render_template('edit_summary.html', summary=summary)

@app.route('/delete_summary/<int:id>')
@login_required
def delete_summary(id):
    summary = Summary.query.get_or_404(id)
    if summary.user_id != current_user.id:
        flash('Unauthorized action.', 'error')
        return redirect(url_for('history'))

    db.session.delete(summary)
    db.session.commit()
    flash('Summary deleted successfully.', 'success')
    return redirect(url_for('history'))

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

if __name__ == "__main__":
    db.create_all()  # Creates the database tables
    app.run(debug=True)
