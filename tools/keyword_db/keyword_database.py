"""
SQLite database for storing LS-DYNA keyword documentation.
"""

import sqlite3
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

class KeywordDatabase:
    def __init__(self, db_path: str = None):
        """Initialize the database connection."""
        if db_path is None:
            db_path = str(Path(__file__).resolve().parents[2] / 'data' / 'archiv' / 'lsdyna_keywords.db')
        
        self.db_path = db_path
        self.conn = None
        self._initialize_database()
    
    def _initialize_database(self):
        """Create the database tables if they don't exist."""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row  # Enable column access by name
        
        with self.conn:
            # Keywords table
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS keywords (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    category TEXT,
                    description TEXT,
                    filename TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Parameters table
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS parameters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    keyword_id INTEGER,
                    param_name TEXT,
                    data_type TEXT,
                    default_value TEXT,
                    description TEXT,
                    is_required BOOLEAN,
                    FOREIGN KEY (keyword_id) REFERENCES keywords (id)
                )
            ''')
            
            # Sections table
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS sections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    keyword_id INTEGER,
                    section_name TEXT,
                    content TEXT,
                    FOREIGN KEY (keyword_id) REFERENCES keywords (id)
                )
            ''')
    
    def add_keyword(self, keyword_data: Dict[str, Any]) -> int:
        """Add a keyword and its data to the database."""
        with self.conn:
            # Insert or update keyword
            cursor = self.conn.execute('''
                INSERT OR REPLACE INTO keywords (name, category, description, filename)
                VALUES (?, ?, ?, ?)
            ''', (
                keyword_data['name'],
                keyword_data.get('category'),
                keyword_data.get('description'),
                keyword_data.get('filename')
            ))
            
            keyword_id = cursor.lastrowid
            
            # Add parameters if they exist
            if 'parameters' in keyword_data:
                self._add_parameters(keyword_id, keyword_data['parameters'])
            
            # Add sections if they exist
            if 'sections' in keyword_data:
                self._add_sections(keyword_id, keyword_data['sections'])
            
            return keyword_id
    
    def _add_parameters(self, keyword_id: int, parameters: List[Dict[str, Any]]):
        """Add parameters for a keyword."""
        for param in parameters:
            self.conn.execute('''
                INSERT INTO parameters 
                (keyword_id, param_name, data_type, default_value, description, is_required)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                keyword_id,
                param.get('name', ''),
                param.get('type', ''),
                param.get('default', ''),
                param.get('description', ''),
                param.get('required', False)
            ))
    
    def _add_sections(self, keyword_id: int, sections: Dict[str, List[str]]):
        """Add sections for a keyword."""
        for section_name, content_list in sections.items():
            # Join the content list into a single string
            content = '\n'.join(str(item) for item in content_list)
            
            self.conn.execute('''
                INSERT INTO sections (keyword_id, section_name, content)
                VALUES (?, ?, ?)
            ''', (keyword_id, section_name, content))
    
    def get_keyword(self, keyword_name: str) -> Optional[Dict]:
        """Retrieve a keyword and its data from the database."""
        cursor = self.conn.cursor()
        
        # Get keyword
        cursor.execute('SELECT * FROM keywords WHERE name = ?', (keyword_name,))
        keyword_row = cursor.fetchone()
        
        if not keyword_row:
            return None
        
        # Convert row to dict
        keyword = dict(keyword_row)
        keyword_id = keyword['id']
        
        # Get parameters
        cursor.execute('SELECT * FROM parameters WHERE keyword_id = ?', (keyword_id,))
        keyword['parameters'] = [dict(row) for row in cursor.fetchall()]
        
        # Get sections
        cursor.execute('SELECT section_name, content FROM sections WHERE keyword_id = ?', (keyword_id,))
        keyword['sections'] = {
            row['section_name']: row['content'].split('\n')
            for row in cursor.fetchall()
        }
        
        return keyword
    
    def search_keywords(self, search_term: str, limit: int = 10) -> List[Dict]:
        """Search for keywords by name or description."""
        cursor = self.conn.cursor()
        
        search_pattern = f'%{search_term}%'
        cursor.execute('''
            SELECT id, name, category, description 
            FROM keywords 
            WHERE name LIKE ? OR description LIKE ?
            LIMIT ?
        ''', (search_pattern, search_pattern, limit))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_keywords_by_category(self, category: str) -> List[Dict]:
        """Get all keywords in a specific category."""
        cursor = self.conn.cursor()
        
        cursor.execute('''
            SELECT id, name, description 
            FROM keywords 
            WHERE category = ?
            ORDER BY name
        ''', (category,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_all_categories(self) -> List[str]:
        """Get all unique categories in the database."""
        cursor = self.conn.cursor()
        cursor.execute('SELECT DISTINCT category FROM keywords WHERE category IS NOT NULL ORDER BY category')
        return [row[0] for row in cursor.fetchall()]
    
    def export_to_json(self, output_file: str = None):
        """Export the entire database to a JSON file."""
        if output_file is None:
            output_file = str(Path(self.db_path).with_suffix('.json'))
        
        cursor = self.conn.cursor()
        
        # Get all keywords
        cursor.execute('SELECT id, name, category, description FROM keywords')
        keywords = []
        
        for row in cursor.fetchall():
            keyword = dict(row)
            keyword_id = keyword['id']
            
            # Get parameters
            cursor2 = self.conn.cursor()
            cursor2.execute('''
                SELECT param_name as name, data_type as type, default_value as default_value, 
                       description, is_required as required
                FROM parameters 
                WHERE keyword_id = ?
            ''', (keyword_id,))
            keyword['parameters'] = [dict(row) for row in cursor2.fetchall()]
            
            # Get sections
            cursor2.execute('''
                SELECT section_name as name, content 
                FROM sections 
                WHERE keyword_id = ?
            ''', (keyword_id,))
            
            sections = {}
            for section_row in cursor2.fetchall():
                section = dict(section_row)
                sections[section['name']] = section['content'].split('\n')
            
            keyword['sections'] = sections
            keywords.append(keyword)
        
        # Write to JSON file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(keywords, f, indent=2, ensure_ascii=False)
        
        return output_file
    
    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def create_database_from_parser(parser_output: List[Dict], db_path: str = None) -> KeywordDatabase:
    """Create a database from parser output."""
    db = KeywordDatabase(db_path)
    
    for keyword_data in parser_output:
        db.add_keyword(keyword_data)
    
    return db


if __name__ == "__main__":
    # Example usage
    with KeywordDatabase() as db:
        # Example: Get all categories
        print("Available categories:")
        for category in db.get_all_categories():
            print(f"- {category}")
        
        # Example: Search for keywords
        print("\nSearch results for 'node':")
        for keyword in db.search_keywords('node'):
            print(f"- {keyword['name']}: {keyword['description']}")
        
        # Example: Export to JSON
        json_file = db.export_to_json()
        print(f"\nDatabase exported to {json_file}")
