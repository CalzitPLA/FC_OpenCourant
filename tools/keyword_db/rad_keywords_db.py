"""
Radioss Keywords Database Module

This module handles the SQLite database for Radioss keywords and their properties.
"""

import os
import sqlite3
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
import FreeCAD

class RadiossKeywordDB:
    def __init__(self, db_path: str = None):
        """Initialize the Radioss keyword database.
        
        Args:
            db_path: Path to the SQLite database file. If None, uses a default location.
        """
        if db_path is None:
            # Default location in FreeCAD user directory
            user_dir = FreeCAD.getUserAppDataDir()
            db_dir = os.path.join(user_dir, 'Mod', 'ORfe')
            os.makedirs(db_dir, exist_ok=True)
            db_path = os.path.join(db_dir, 'radioss_keywords.db')
            
        self.db_path = db_path
        self.conn = None
        self._initialize_database()
    
    def _get_connection(self):
        """Get a database connection, creating one if it doesn't exist."""
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row  # Access columns by name
        return self.conn
    
    def _initialize_database(self):
        """Initialize the database with required tables if they don't exist."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Create categories table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            description TEXT
        )
        ''')
        
        # Create keywords table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS keywords (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            category_id INTEGER,
            description TEXT,
            syntax TEXT,
            required_parameters TEXT,  -- JSON array of required parameters
            optional_parameters TEXT,  -- JSON array of optional parameters
            example TEXT,
            FOREIGN KEY (category_id) REFERENCES categories(id)
        )
        ''')
        
        # Create parameters table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS parameters (
            id INTEGER PRIMARY KEY,
            keyword_id INTEGER,
            name TEXT NOT NULL,
            type TEXT,
            required BOOLEAN DEFAULT 0,
            description TEXT,
            default_value TEXT,
            FOREIGN KEY (keyword_id) REFERENCES keywords(id)
        )
        ''')
        
        # Create index for faster lookups
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_keywords_name ON keywords(name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_keywords_category ON keywords(category_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_parameters_keyword ON parameters(keyword_id)')
        
        conn.commit()
    
    def add_category(self, name: str, description: str = None) -> int:
        """Add a new category to the database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Try to get existing category
        cursor.execute('SELECT id FROM categories WHERE name = ?', (name,))
        result = cursor.fetchone()
        
        if result:
            return result[0]  # Return existing category ID
            
        # Insert new category
        cursor.execute(
            'INSERT INTO categories (name, description) VALUES (?, ?)',
            (name, description)
        )
        conn.commit()
        return cursor.lastrowid
    
    def add_keyword(self, name: str, category_name: str, description: str = None, 
                   syntax: str = None, required_params: list = None, 
                   optional_params: list = None, example: str = None) -> int:
        """Add a new keyword to the database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Get or create category
        category_id = self.add_category(category_name)
        
        # Check if keyword already exists
        cursor.execute('SELECT id FROM keywords WHERE name = ?', (name,))
        result = cursor.fetchone()
        
        if result:
            return result[0]  # Return existing keyword ID
        
        # Insert new keyword
        cursor.execute(
            '''
            INSERT INTO keywords 
            (name, category_id, description, syntax, required_parameters, optional_parameters, example)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                name,
                category_id,
                description,
                syntax,
                json.dumps(required_params) if required_params else None,
                json.dumps(optional_params) if optional_params else None,
                example
            )
        )
        keyword_id = cursor.lastrowid
        
        # Add parameters if provided
        if required_params:
            for param in required_params:
                self._add_parameter(keyword_id, param, required=True)
                
        if optional_params:
            for param in optional_params:
                self._add_parameter(keyword_id, param, required=False)
        
        conn.commit()
        return keyword_id
    
    def _add_parameter(self, keyword_id: int, param: dict, required: bool = False):
        """Add a parameter for a keyword."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            '''
            INSERT INTO parameters 
            (keyword_id, name, type, required, description, default_value)
            VALUES (?, ?, ?, ?, ?, ?)
            ''',
            (
                keyword_id,
                param.get('name', ''),
                param.get('type', 'string'),
                1 if required else 0,
                param.get('description', ''),
                param.get('default_value')
            )
        )
    
    def get_keyword(self, name: str) -> Optional[dict]:
        """Get a keyword by name with its parameters."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Get keyword info
        cursor.execute('''
            SELECT k.*, c.name as category_name 
            FROM keywords k
            LEFT JOIN categories c ON k.category_id = c.id
            WHERE k.name = ?
        ''', (name,))
        
        keyword = cursor.fetchone()
        if not keyword:
            return None
            
        # Convert to dict
        keyword_dict = dict(keyword)
        
        # Get parameters
        cursor.execute('''
            SELECT * FROM parameters 
            WHERE keyword_id = ?
            ORDER BY id
        ''', (keyword_dict['id'],))
        
        keyword_dict['parameters'] = [dict(row) for row in cursor.fetchall()]
        
        # Parse JSON fields
        for field in ['required_parameters', 'optional_parameters']:
            if keyword_dict[field]:
                try:
                    keyword_dict[field] = json.loads(keyword_dict[field])
                except (json.JSONDecodeError, TypeError):
                    keyword_dict[field] = []
        
        return keyword_dict
    
    def get_keywords_by_category(self, category_name: str) -> List[dict]:
        """Get all keywords in a category."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT k.*, c.name as category_name 
            FROM keywords k
            JOIN categories c ON k.category_id = c.id
            WHERE c.name = ?
            ORDER BY k.name
        ''', (category_name,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_all_categories(self) -> List[dict]:
        """Get all categories with keyword counts."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT c.*, COUNT(k.id) as keyword_count
            FROM categories c
            LEFT JOIN keywords k ON c.id = k.category_id
            GROUP BY c.id, c.name
            ORDER BY c.name
        ''')
        
        return [dict(row) for row in cursor.fetchall()]
    
    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def initialize_database(db_path: str = None) -> RadiossKeywordDB:
    """Initialize the Radioss keyword database with default data."""
    db = RadiossKeywordDB(db_path)
    
    # Add categories and keywords here
    # Example:
    # db.add_keyword(
    #     name="*NODE",
    #     category_name="NODE",
    #     description="Defines a node number and nodal coordinates in the global coordinate system.",
    #     syntax="*NODE\nNodeID, X, Y, Z, TC, RC",
    #     required_params=[
    #         {"name": "NodeID", "type": "integer", "description": "Node identification number"},
    #         {"name": "X", "type": "float", "description": "X-coordinate"},
    #         {"name": "Y", "type": "float", "description": "Y-coordinate"},
    #         {"name": "Z", "type": "float", "description": "Z-coordinate"}
    #     ],
    #     optional_params=[
    #         {"name": "TC", "type": "integer", "description": "Translation constraint code"},
    #         {"name": "RC", "type": "integer", "description": "Rotational constraint code"}
    #     ]
    # )
    
    return db


if __name__ == "__main__":
    # Test the database
    with RadiossKeywordDB(":memory:") as db:
        # Add test data
        db.add_keyword(
            name="*NODE",
            category_name="NODE",
            description="Defines a node number and nodal coordinates in the global coordinate system.",
            syntax="*NODE\nNodeID, X, Y, Z, TC, RC",
            required_params=[
                {"name": "NodeID", "type": "integer", "description": "Node identification number"},
                {"name": "X", "type": "float", "description": "X-coordinate"},
                {"name": "Y", "type": "float", "description": "Y-coordinate"},
                {"name": "Z", "type": "float", "description": "Z-coordinate"}
            ],
            optional_params=[
                {"name": "TC", "type": "integer", "description": "Translation constraint code"},
                {"name": "RC", "type": "integer", "description": "Rotational constraint code"}
            ]
        )
        
        # Query test
        node_keyword = db.get_keyword("*NODE")
        print(f"Keyword: {node_keyword['name']}")
        print(f"Description: {node_keyword['description']}")
        print("Required parameters:")
        for param in node_keyword['required_parameters']:
            print(f"  - {param['name']}: {param['description']}")
