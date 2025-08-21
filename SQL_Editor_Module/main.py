# main.py - FIXED VERSION
from fastapi import FastAPI, Request, Form, File, UploadFile, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import io
import base64
from io import BytesIO
import matplotlib.pyplot as plt
import seaborn as sns
import mysql.connector
from mysql.connector import Error
import json
import os
from typing import Optional, Dict, Any
import logging
import sqlite3

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Add CORS middleware to allow frontend-backend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files and setup templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Database configuration - with error handling
DB_CONFIG = {
    'host': '127.0.0.1',
    'database': 'hackathon',
    'user': 'root',
    'password': 'aj11anuj',
    'auth_plugin': 'mysql_native_password'
}

# SQLite fallback configuration
SQLITE_DB_PATH = "hackathon.db"

# Initialize SQLite database
def init_sqlite_db():
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        cursor = conn.cursor()
        
        # Create table if not exists
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS uploaded_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            age INTEGER,
            city TEXT
        )
        """)
        
        conn.commit()
        conn.close()
        logger.info("SQLite database initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing SQLite database: {str(e)}")

# Initialize SQLite on startup
init_sqlite_db()

# In-memory storage for the dataset
current_dataset = None
current_dataset_name = ""

def get_db_connection():
    """Create and return a database connection with better error handling"""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        logger.info("MySQL database connection established successfully")
        return connection
    except Error as e:
        logger.error(f"MySQL database connection failed: {str(e)}")
        # Fallback to SQLite
        try:
            conn = sqlite3.connect(SQLITE_DB_PATH)
            conn.row_factory = sqlite3.Row
            logger.info("Using SQLite database as fallback")
            return conn
        except Exception as sqlite_error:
            logger.error(f"SQLite connection also failed: {str(sqlite_error)}")
            raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")

def fig_to_uri(fig):
    """Convert matplotlib figure to base64 encoded image"""
    buf = BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    return "data:image/png;base64," + base64.b64encode(buf.read()).decode('utf-8')

@app.get("/")
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# SQL execution endpoint (replaces execute.php and query.php)
@app.post("/execute-sql")
async def execute_sql(request: Request):
    try:
        data = await request.json()
        sql_query = data.get('sql', '')
        
        if not sql_query:
            return {"error": "No SQL query provided"}
        
        logger.info(f"Executing SQL: {sql_query[:100]}...")  # Log first 100 chars
        
        connection = get_db_connection()
        
        # Check if it's SQLite or MySQL
        if isinstance(connection, sqlite3.Connection):
            cursor = connection.cursor()
            cursor.execute(sql_query)
            
            # For SELECT queries
            if sql_query.strip().lower().startswith('select'):
                result = cursor.fetchall()
                # Convert sqlite3.Row objects to dictionaries
                result = [dict(row) for row in result]
                logger.info(f"Query returned {len(result)} rows")
                return result
            else:
                connection.commit()
                logger.info(f"Query executed, {cursor.rowcount} rows affected")
                return {"success": f"Query executed successfully. Rows affected: {cursor.rowcount}"}
        else:
            # MySQL connection
            cursor = connection.cursor(dictionary=True)
            cursor.execute(sql_query)
            
            # For SELECT queries
            if cursor.description:
                result = cursor.fetchall()
                logger.info(f"Query returned {len(result)} rows")
                return result
            # For INSERT, UPDATE, DELETE queries
            else:
                connection.commit()
                logger.info(f"Query executed, {cursor.rowcount} rows affected")
                return {"success": f"Query executed successfully. Rows affected: {cursor.rowcount}"}
            
    except Error as e:
        logger.error(f"Database error: {str(e)}")
        return {"error": f"Database error: {str(e)}"}
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return {"error": f"Unexpected error: {str(e)}"}
    finally:
        if 'connection' in locals():
            try:
                if hasattr(connection, 'is_connected') and connection.is_connected():
                    cursor.close()
                    connection.close()
                elif hasattr(connection, 'close'):
                    connection.close()
            except:
                pass

# Dataset upload endpoint (replaces upload.php) - COMPLETELY REWRITTEN
@app.post("/upload-dataset")
async def upload_dataset(file: UploadFile = File(...)):
    global current_dataset, current_dataset_name
    
    try:
        # Get file extension
        filename = file.filename
        current_dataset_name = filename
        logger.info(f"Uploading file: {filename}")
        
        if not filename:
            return {"error": "No file provided"}
        
        # Read file content
        contents = await file.read()
        
        # Process the file based on extension
        if filename.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(contents))
        elif filename.endswith('.xlsx') or filename.endswith('.xls'):
            df = pd.read_excel(io.BytesIO(contents))
        else:
            return {"error": "Unsupported file format. Please upload CSV or Excel file."}
        
        current_dataset = df
        logger.info(f"Dataset loaded with shape: {df.shape}")
        
        # Try to save to database
        db_message = ""
        rows_inserted = 0
        
        try:
            connection = get_db_connection()
            
            if isinstance(connection, sqlite3.Connection):
                # SQLite
                cursor = connection.cursor()
                
                # Clear existing data
                cursor.execute("DELETE FROM uploaded_data")
                
                # Insert new data - handle different column names
                for _, row in df.iterrows():
                    # Map common column names or use defaults
                    name = row.get('name', row.get('Name', row.get('NAME', '')))
                    age = row.get('age', row.get('Age', row.get('AGE', 0)))
                    city = row.get('city', row.get('City', row.get('CITY', '')))
                    
                    # Convert age to integer if possible
                    try:
                        age = int(age)
                    except (ValueError, TypeError):
                        age = 0
                    
                    cursor.execute(
                        "INSERT INTO uploaded_data (name, age, city) VALUES (?, ?, ?)",
                        (str(name), age, str(city))
                    )
                
                connection.commit()
                rows_inserted = len(df)
                db_message = f"Data saved to SQLite database ({rows_inserted} rows)"
                
            else:
                # MySQL
                cursor = connection.cursor()
                
                # Create table if not exists
                create_table_sql = """
                CREATE TABLE IF NOT EXISTS uploaded_data (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(255),
                    age INT,
                    city VARCHAR(255)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
                cursor.execute(create_table_sql)
                
                # Clear existing data
                cursor.execute("TRUNCATE TABLE uploaded_data")
                
                # Insert new data - handle different column names
                for _, row in df.iterrows():
                    # Map common column names or use defaults
                    name = row.get('name', row.get('Name', row.get('NAME', '')))
                    age = row.get('age', row.get('Age', row.get('AGE', 0)))
                    city = row.get('city', row.get('City', row.get('CITY', '')))
                    
                    # Convert age to integer if possible
                    try:
                        age = int(age)
                    except (ValueError, TypeError):
                        age = 0
                    
                    cursor.execute(
                        "INSERT INTO uploaded_data (name, age, city) VALUES (%s, %s, %s)",
                        (str(name), age, str(city))
                    )
                
                connection.commit()
                rows_inserted = len(df)
                db_message = f"Data saved to MySQL database ({rows_inserted} rows)"
            
            logger.info(db_message)
            
        except Exception as db_error:
            db_message = f"Database save failed: {str(db_error)}"
            logger.error(db_message)
            rows_inserted = 0
        finally:
            if 'connection' in locals():
                try:
                    if hasattr(connection, 'is_connected') and connection.is_connected():
                        cursor.close()
                        connection.close()
                    elif hasattr(connection, 'close'):
                        connection.close()
                except:
                    pass
        
        # Convert numpy array to list for JSON serialization
        shape_list = list(df.shape)
        
        return {
            "success": True,
            "message": "Dataset uploaded successfully", 
            "shape": shape_list,
            "columns": list(df.columns),
            "dtypes": df.dtypes.astype(str).to_dict(),
            "rowsInserted": rows_inserted,
            "dbStatus": db_message
        }
        
    except Exception as e:
        error_msg = f"Could not process file: {str(e)}"
        logger.error(error_msg)
        return {"error": error_msg}

# Data analysis endpoint
@app.get("/analyze")
async def analyze_dataset(action: str, column: str = None):
    global current_dataset
    
    if current_dataset is None:
        return {"error": "No dataset uploaded. Please upload a dataset first."}
    
    try:
        df = current_dataset
        logger.info(f"Analysis action: {action}, column: {column}")
        
        # Basic Analysis
        if action == "summary":
            result = df.describe(include='all').fillna('').to_html(classes='data-table')
        elif action == "head":
            result = df.head().fillna('').to_html(classes='data-table')
        elif action == "columns":
            result = list(df.columns)
        elif action == "missing":
            result = df.isna().sum().to_dict()
        elif action == "dtypes":
            result = df.dtypes.astype(str).to_dict()
        
        # Visualization with Matplotlib
        elif action == "histogram" and column:
            if column not in df.columns:
                return {"error": f"Column '{column}' not found in dataset"}
            plt.figure(figsize=(10, 6))
            df[column].hist()
            plt.title(f"Histogram of {column}")
            plt.xlabel(column)
            plt.ylabel('Frequency')
            result = fig_to_uri(plt.gcf())
            plt.close()
        elif action == "boxplot" and column:
            if column not in df.columns:
                return {"error": f"Column '{column}' not found in dataset"}
            plt.figure(figsize=(10, 6))
            sns.boxplot(y=df[column])
            plt.title(f"Box Plot of {column}")
            result = fig_to_uri(plt.gcf())
            plt.close()
        elif action == "scatter" and column:
            if column not in df.columns:
                return {"error": f"Column '{column}' not found in dataset"}
            if len(df.columns) < 2:
                return {"error": "Need at least two columns for scatter plot"}
            # Find another numeric column
            numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
            if column in numeric_cols:
                numeric_cols.remove(column)
            if not numeric_cols:
                return {"error": "No other numeric columns found for scatter plot"}
            y_col = numeric_cols[0]
            plt.figure(figsize=(10, 6))
            plt.scatter(df[column], df[y_col])
            plt.xlabel(column)
            plt.ylabel(y_col)
            plt.title(f"Scatter Plot: {column} vs {y_col}")
            result = fig_to_uri(plt.gcf())
            plt.close()
        elif action == "correlation":
            numeric_df = df.select_dtypes(include=['number'])
            if len(numeric_df.columns) < 2:
                return {"error": "Need at least two numeric columns for correlation"}
            plt.figure(figsize=(10, 8))
            sns.heatmap(numeric_df.corr(), annot=True, cmap='coolwarm', center=0)
            plt.title("Correlation Matrix")
            result = fig_to_uri(plt.gcf())
            plt.close()
        elif action == "value_counts" and column:
            if column not in df.columns:
                return {"error": f"Column '{column}' not found in dataset"}
            result = df[column].value_counts().to_dict()
        else:
            return {"error": "Invalid action or missing column parameter"}
        
        return {"result": result}
    except Exception as e:
        error_msg = f"Analysis error: {str(e)}"
        logger.error(error_msg)
        return {"error": error_msg}

# Health check endpoint
@app.get("/health")
async def health_check():
    try:
        connection = get_db_connection()
        if hasattr(connection, 'close'):
            connection.close()
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "healthy", "database": f"disconnected: {str(e)}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)