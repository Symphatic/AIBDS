import unittest
from app import app

class TestSummarizer(unittest.TestCase):

    def setUp(self):
        # Set up the test client
        self.app = app.test_client()
        self.app.testing = True

    def test_home_page(self):
        # Test the home page loads correctly
        result = self.app.get('/')
        self.assertEqual(result.status_code, 200)
        self.assertIn(b'AI Document Summarizer', result.data)

    def test_empty_input(self):
        # Test empty input returns an error
        result = self.app.post('/summarize', data=dict(content=''))
        self.assertIn(b'Input text cannot be empty', result.data)

    def test_long_input(self):
        # Test overly long input returns an error
        long_text = "word " * 1001  # 1001 words
        result = self.app.post('/summarize', data=dict(content=long_text))
        self.assertIn(b'Input text is too long', result.data)

    def test_valid_input(self):
        # Test valid input returns a summary
        valid_text = "Artificial Intelligence is a branch of computer science."
        result = self.app.post('/summarize', data=dict(content=valid_text))
        self.assertIn(b'Summary', result.data)

if __name__ == '__main__':
    unittest.main()
