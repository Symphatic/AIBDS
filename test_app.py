import unittest
from app import app, db, User  # Adjust imports based on your app structure
from flask import url_for

class TestApp(unittest.TestCase):

    def setUp(self):
        # Configure the app for testing
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'  # Use in-memory DB for testing
        app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for testing if using WTForms
        self.app = app.test_client()
        # Initialize the database
        with app.app_context():
            db.create_all()

    def tearDown(self):
        # Clean up the database
        with app.app_context():
            db.session.remove()
            db.drop_all()

    # Summarizer Tests
    def test_home_page(self):
        result = self.app.get('/')
        self.assertEqual(result.status_code, 200)
        self.assertIn(b'AI Document Summarizer', result.data)

    def test_empty_input(self):
        result = self.app.post('/summarize', data=dict(content=''))
        self.assertIn(b'Input text cannot be empty', result.data)

    def test_long_input(self):
        long_text = "word " * 1001
        result = self.app.post('/summarize', data=dict(content=long_text))
        self.assertIn(b'Input text is too long', result.data)

    def test_valid_input_short(self):
        valid_text = "Artificial Intelligence is a branch of computer science."
        result = self.app.post('/summarize', data=dict(content=valid_text, length='short'))
        self.assertIn(b'Summary', result.data)

    def test_valid_input_medium(self):
        valid_text = "Artificial Intelligence is a branch of computer science."
        result = self.app.post('/summarize', data=dict(content=valid_text, length='medium'))
        self.assertIn(b'Summary', result.data)

    def test_valid_input_long(self):
        valid_text = "Artificial Intelligence is a branch of computer science."
        result = self.app.post('/summarize', data=dict(content=valid_text, length='long'))
        self.assertIn(b'Summary', result.data)

    def test_valid_input_spanish(self):
        valid_text = "La inteligencia artificial es una rama de la informática."
        result = self.app.post('/summarize', data=dict(content=valid_text, length='medium'))
        self.assertIn(b'Summary', result.data)

    # Authentication Tests
    def test_register(self):
        response = self.app.post('/register', data=dict(
            username="testuser",
            email="testuser@example.com",
            password="password"
        ), follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        # Check if user was created
        with app.app_context():
            user = User.query.filter_by(username="testuser").first()
            self.assertIsNotNone(user)

    def test_register_existing_user(self):
        # First registration
        self.app.post('/register', data=dict(
            username="testuser",
            email="testuser@example.com",
            password="password"
        ), follow_redirects=True)
        # Attempt to register again with same username
        response = self.app.post('/register', data=dict(
            username="testuser",
            email="testuser2@example.com",
            password="password"
        ), follow_redirects=True)
        self.assertIn(b'Username already exists', response.data)

    def test_login(self):
        # Register a user first
        self.app.post('/register', data=dict(
            username="testuser",
            email="testuser@example.com",
            password="password"
        ), follow_redirects=True)
        # Attempt to login
        response = self.app.post('/login', data=dict(
            username="testuser",
            password="password"
        ), follow_redirects=True)
        self.assertIn(b'Logout', response.data)  # Assuming 'Logout' is visible after login

    def test_login_invalid_credentials(self):
        # Attempt to login without registering
        response = self.app.post('/login', data=dict(
            username="nonexistent",
            password="password"
        ), follow_redirects=True)
        self.assertIn(b'Invalid username or password', response.data)

    def test_2fa_verification(self):
        # Register and login a user first
        self.app.post('/register', data=dict(
            username="testuser",
            email="testuser@example.com",
            password="password"
        ), follow_redirects=True)
        login_response = self.app.post('/login', data=dict(
            username="testuser",
            password="password"
        ), follow_redirects=True)
        # Assuming 2FA is required after login, simulate entering the 2FA code
        # For testing, you need to mock or set the expected code
        # Here, assuming the code is '123456'
        response = self.app.post('/verify_2fa', data=dict(
            code='123456'
        ), follow_redirects=True)
        self.assertIn(b'2FA verification successful', response.data)

    def test_logout(self):
        # Register and login a user first
        self.app.post('/register', data=dict(
            username="testuser",
            email="testuser@example.com",
            password="password"
        ), follow_redirects=True)
        self.app.post('/login', data=dict(
            username="testuser",
            password="password"
        ), follow_redirects=True)
        # Logout
        response = self.app.get('/logout', follow_redirects=True)
        self.assertIn(b'Login', response.data)  # Assuming 'Login' link is visible after logout

if __name__ == '__main__':
    unittest.main()
