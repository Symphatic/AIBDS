import unittest
from app import app

class TestSummarizer(unittest.TestCase):

    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

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

if __name__ == '__main__':
    unittest.main()
