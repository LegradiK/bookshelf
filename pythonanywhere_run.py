import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, 'data.env'))

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)