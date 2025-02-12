import os
import sqlite3
import pyodbc
import db_connector
from dotenv import load_dotenv
from openai import OpenAI
import re
import logging
from typing import Dict, List, Tuple, Optional

# Configure logging
logging.basicConfig(
    filename="query_ai.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

class SchemaValidator:
    def __init__(self, schema_file: str = "schema_cache.db"):
        self.schema_file = schema_file
        self.schema_map: Dict[str, str] = {}
        self.column_map: Dict[str, List[Tuple[str, str]]] = {}
        self.init_schema_db()
        self.load_schemas()

    def init_schema_db(self) -> None:
        """Initialize SQLite database for schema caching"""
        conn = sqlite3.connect(self.schema_file)
        cursor = conn.cursor()
        
        # Create tables with constraints to ensure data integrity
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS table_schemas (
                schema_name TEXT NOT NULL,
                table_name TEXT PRIMARY KEY,
                UNIQUE(schema_name, table_name)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS column_details (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                schema_name TEXT NOT NULL,
                table_name TEXT NOT NULL,
                column_name TEXT NOT NULL,
                data_type TEXT NOT NULL,
                UNIQUE(schema_name, table_name, column_name),
                FOREIGN KEY (table_name) REFERENCES table_schemas(table_name)
            )
        """)

        conn.commit()
        conn.close()

    def load_schemas(self) -> None:
        """Load schema information from the database"""
        conn = db_connector.connect_to_db()
        if not conn:
            logging.error("Failed to connect to database")
            return

        cursor = conn.cursor()
        
        # Get table schemas
        cursor.execute("""
            SELECT TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, DATA_TYPE 
            FROM INFORMATION_SCHEMA.COLUMNS 
            ORDER BY TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME
        """)
        
        # Build schema and column maps
        for row in cursor.fetchall():
            schema_name = row.TABLE_SCHEMA
            table_name = row.TABLE_NAME
            column_name = row.COLUMN_NAME
            data_type = row.DATA_TYPE

            full_table_name = f"{schema_name}.{table_name}"
            
            # Update schema map
            self.schema_map[table_name] = schema_name
            
            # Update column map
            if full_table_name not in self.column_map:
                self.column_map[full_table_name] = []
            self.column_map[full_table_name].append((column_name, data_type))

        conn.close()
        self._cache_schemas()

    def _cache_schemas(self) -> None:
        """Cache schema information in SQLite"""
        sqlite_conn = sqlite3.connect(self.schema_file)
        cursor = sqlite_conn.cursor()

        # Clear existing data
        cursor.execute("DELETE FROM column_details")
        cursor.execute("DELETE FROM table_schemas")

        # Cache new schema information
        for table_name, schema_name in self.schema_map.items():
            cursor.execute(
                "INSERT INTO table_schemas (schema_name, table_name) VALUES (?, ?)",
                (schema_name, table_name)
            )

        for full_table_name, columns in self.column_map.items():
            schema_name, table_name = full_table_name.split(".")
            for column_name, data_type in columns:
                cursor.execute("""
                    INSERT INTO column_details 
                    (schema_name, table_name, column_name, data_type)
                    VALUES (?, ?, ?, ?)
                """, (schema_name, table_name, column_name, data_type))

        sqlite_conn.commit()
        sqlite_conn.close()

    def get_schema_details(self) -> str:
        """Generate detailed schema information for AI prompt"""
        details = []
        for full_table_name, columns in self.column_map.items():
            column_details = [f"{col[0]} ({col[1]})" for col in columns]
            details.append(f"{full_table_name}:\n  " + "\n  ".join(column_details))
        return "\n\n".join(details)

    def validate_query(self, sql_query: str) -> Tuple[bool, str]:
        """Validate SQL query against known schema with improved alias handling"""
        # Remove string literals to avoid false matches
        cleaned_query = re.sub(r"'[^']*'", "", sql_query)
        
        # Extract table references and their aliases
        table_pattern = r'\b(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*\.?[a-zA-Z0-9_]*)\s+(?:AS\s+)?([a-zA-Z0-9_]+)?'
        table_matches = re.finditer(table_pattern, cleaned_query, re.IGNORECASE)
        
        # Build map of aliases to full table names
        alias_map = {}
        for match in table_matches:
            table_ref = match.group(1)
            alias = match.group(2) if match.group(2) else table_ref.split('.')[-1]
            
            # Handle fully qualified and unqualified table names
            if '.' in table_ref:
                schema, table_name = table_ref.split('.')
                full_table_name = f"{schema}.{table_name}"
            else:
                if table_ref not in self.schema_map:
                    return False, f"Invalid table: {table_ref}"
                full_table_name = f"{self.schema_map[table_ref]}.{table_ref}"
            
            alias_map[alias.lower()] = full_table_name
            
            # Validate table exists
            if full_table_name not in self.column_map:
                return False, f"Invalid table: {full_table_name}"
        
        # Extract and validate column references
        # Look for patterns like "table.column" or "alias.column"
        column_pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\.\s*([a-zA-Z_][a-zA-Z0-9_]*)'
        column_matches = re.finditer(column_pattern, cleaned_query)
        
        for match in column_matches:
            table_or_alias = match.group(1).lower()
            column = match.group(2)
            
            # Skip if it's a schema reference
            if table_or_alias in ['dbo', 'production', 'sales', 'person', 'humanresources']:
                continue
                
            # Get the full table name from the alias map
            full_table_name = alias_map.get(table_or_alias)
            if not full_table_name:
                # Check if it's a direct table reference
                if table_or_alias in self.schema_map:
                    full_table_name = f"{self.schema_map[table_or_alias]}.{table_or_alias}"
                else:
                    continue  # Skip validation if we can't determine the table
            
            # Validate the column exists in the table
            valid_columns = {col[0].lower() for col in self.column_map[full_table_name]}
            if column.lower() not in valid_columns:
                return False, f"Invalid column: {column} in table {full_table_name}"
        
        return True, "Query validation passed"

class DatabaseQueryAI:
    def __init__(self):
        load_dotenv()
        self.schema_validator = SchemaValidator()
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def generate_query(self, natural_language_query: str) -> str:
        """Generate SQL query from natural language input"""
        schema_details = self.schema_validator.get_schema_details()
        
        prompt = f"""
        You are a precise SQL query generator for Microsoft SQL Server (T-SQL).
        
        IMPORTANT: Only use columns that exist in the schema below. Do not hallucinate columns.
        
        Available Schema:
        {schema_details}
        
        Rules:
        1. Return ONLY the SQL query, no explanations
        2. Only use columns from the provided schema
        3. Always qualify column names with table/view names
        4. Use explicit column names, never SELECT *
        5. Only join tables where relationships are clear from schema
        
        User Query: {natural_language_query}
        """

        response = self.client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1  # Lower temperature for more consistent output
        )

        sql_query = response.choices[0].message.content.strip()
        return self._clean_query(sql_query)

    def _clean_query(self, query: str) -> str:
        """Clean and standardize the generated query"""
        query = query.replace("`", "")
        query = re.sub(r"\bLIMIT\s+\d+\b", "", query, flags=re.IGNORECASE)
        query = query.lstrip("sql").strip()
        return query

    def execute_query(self, sql_query: str, user_query: str) -> str:
        """Execute and format query results"""
        # Validate query against schema
        is_valid, validation_message = self.schema_validator.validate_query(sql_query)
        if not is_valid:
            return f"❌ {validation_message}"

        conn = db_connector.connect_to_db()
        if not conn:
            return "❌ Database connection error"

        try:
            cursor = conn.cursor()
            cursor.execute(sql_query)
            
            if cursor.description is None:
                return "✅ Query executed successfully (no results)"

            columns = [column[0] for column in cursor.description]
            rows = cursor.fetchall()
            results = [dict(zip(columns, row)) for row in rows]

            return self._format_results(results, user_query)

        except pyodbc.Error as e:
            logging.error(f"Query execution error: {e}")
            return f"❌ Query execution error: {str(e)}"
        finally:
            conn.close()

    def _format_results(self, results: List[Dict], user_query: str) -> str:
        """Format query results as human-readable text"""
        prompt = f"""
        Convert these database results into a clear, concise summary:
        
        User Question: {user_query}
        Results: {results}
        """

        response = self.client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        
        return response.choices[0].message.content.strip()

def main():
    db_ai = DatabaseQueryAI()
    while True:
        try:
            user_query = input("\nAsk your database (or 'exit' to quit): ")
            if user_query.lower() == 'exit':
                break

            sql_query = db_ai.generate_query(user_query)
            print("\nGenerated SQL Query:")
            print(sql_query)

            results = db_ai.execute_query(sql_query, user_query)
            print("\nResults:")
            print(results)

        except Exception as e:
            logging.error(f"Error: {str(e)}")
            print(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()