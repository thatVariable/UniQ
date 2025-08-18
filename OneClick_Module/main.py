from fastapi import FastAPI, Request, Form, File, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import pandas as pd
import io
import base64
from io import BytesIO
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Optional

app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="templates")

# In-memory storage for the dataset
current_dataset = None
current_dataset_name = ""

def fig_to_uri(fig):
    """Convert matplotlib figure to base64 encoded image"""
    buf = BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    return "data:image/png;base64," + base64.b64encode(buf.read()).decode('utf-8')

@app.get("/")
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/upload")
async def upload_dataset(file: UploadFile = File(...)):
    global current_dataset, current_dataset_name
    try:
        # Get file extension
        filename = file.filename
        current_dataset_name = filename
        if filename.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(await file.read()))
        elif filename.endswith('.xlsx') or filename.endswith('.xls'):
            df = pd.read_excel(io.BytesIO(await file.read()))
        else:
            return {"error": "Unsupported file format. Please upload CSV or Excel file."}
        
        current_dataset = df
        return {
            "message": "Dataset uploaded successfully", 
            "shape": df.shape,
            "columns": list(df.columns),
            "dtypes": df.dtypes.astype(str).to_dict()
        }
    except Exception as e:
        return {"error": f"Could not read file: {str(e)}"}

@app.get("/analyze")
async def analyze_dataset(action: str, column: str = None):
    global current_dataset
    
    if current_dataset is None:
        return {"error": "No dataset uploaded"}
    
    try:
        df = current_dataset
        
        # Basic Analysis
        if action == "summary":
            result = df.describe(include='all').to_html()
        elif action == "head":
            result = df.head().to_html()
        elif action == "columns":
            result = list(df.columns)
        elif action == "missing":
            result = df.isna().sum().to_dict()
        elif action == "dtypes":
            result = df.dtypes.astype(str).to_dict()
        
        # Visualization with Matplotlib
        elif action == "histogram" and column:
            plt.figure()
            df[column].hist()
            plt.title(f"Histogram of {column}")
            result = fig_to_uri(plt.gcf())
            plt.close()
        elif action == "boxplot" and column:
            plt.figure()
            sns.boxplot(y=df[column])
            plt.title(f"Box Plot of {column}")
            result = fig_to_uri(plt.gcf())
            plt.close()
        elif action == "scatter" and column:
            if len(df.columns) > 1:
                y_col = df.columns[1] if column == df.columns[0] else df.columns[0]
                plt.figure()
                plt.scatter(df[column], df[y_col])
                plt.xlabel(column)
                plt.ylabel(y_col)
                plt.title(f"Scatter Plot: {column} vs {y_col}")
                result = fig_to_uri(plt.gcf())
                plt.close()
            else:
                result = {"error": "Need at least two columns for scatter plot"}
        elif action == "correlation":
            numeric_df = df.select_dtypes(include=['number'])
            if len(numeric_df.columns) > 1:
                plt.figure(figsize=(10, 8))
                sns.heatmap(numeric_df.corr(), annot=True, cmap='coolwarm')
                plt.title("Correlation Matrix")
                result = fig_to_uri(plt.gcf())
                plt.close()
            else:
                result = {"error": "Need at least two numeric columns for correlation"}
        elif action == "value_counts" and column:
            result = df[column].value_counts().to_dict()
        else:
            return {"error": "Invalid action or missing column parameter"}
        
        return {"result": result}
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)