import sqlite3
import json
import logging
import os
from datetime import datetime

logger = logging.getLogger("database")

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "inspection_history.db")

def init_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Create inspections table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS inspections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                frame_id TEXT NOT NULL,
                model TEXT NOT NULL,
                check_time DATETIME NOT NULL,
                final_result TEXT NOT NULL,
                bolt_data TEXT NOT NULL, -- JSON string of {bolt_id: status}
                images TEXT NOT NULL     -- JSON string of {cam_step: image_path}
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info(f"Database initialized at {DB_PATH}")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")

def save_inspection(frame_id, model, final_result, bolt_data, images):
    """
    Saves an inspection record to the database.
    bolt_data: dict of bolt statuses
    images: dict of image paths saved on disk
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        check_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        bolt_json = json.dumps(bolt_data)
        images_json = json.dumps(images)
        
        cursor.execute('''
            INSERT INTO inspections (frame_id, model, check_time, final_result, bolt_data, images)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (frame_id, model, check_time, final_result, bolt_json, images_json))
        
        conn.commit()
        conn.close()
        logger.info(f"Saved inspection for frame {frame_id} with result {final_result}")
    except Exception as e:
        logger.error(f"Error saving inspection to database: {e}")

def get_history(limit=50):
    """
    Retrieves the most recent inspection records.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row # To access columns by name
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM inspections 
            ORDER BY check_time DESC 
            LIMIT ?
        ''', (limit,))
        
        rows = cursor.fetchall()
        
        # Convert rows to a list of dicts, parsing JSON back to objects
        history = []
        for row in rows:
            record = dict(row)
            record['bolt_data'] = json.loads(record['bolt_data'])
            record['images'] = json.loads(record['images'])
            history.append(record)
            
        conn.close()
        return history
    except Exception as e:
        logger.error(f"Error retrieving history: {e}")
        return []
