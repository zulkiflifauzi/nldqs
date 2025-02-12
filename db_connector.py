import pyodbc
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def connect_to_db():
    try:
        conn = pyodbc.connect(
            f"DRIVER={{SQL Server}};"
            f"SERVER={os.getenv('DB_SERVER')};"
            f"DATABASE={os.getenv('DB_DATABASE')};"
            f"UID={os.getenv('DB_USERNAME')};"
            f"PWD={os.getenv('DB_PASSWORD')}"
        )
        return conn
    except Exception as e:
        print("Database connection failed:", e)
        return None
