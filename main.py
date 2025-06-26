from flask import Flask, render_template, jsonify, request
import pandas as pd
from flask import send_from_directory
import os
from datetime import datetime
import json
import mimetypes
import re

# World Bank data typically comes in three files:
# 1. [Indicator]_Data.csv - Contains the actual data
# 2. [Indicator]_Metadata.csv - Contains information about the indicator
# 3. [Indicator]_Footnotes.csv - Contains notes about specific data points

app = Flask(__name__)
df = pd.read_csv('data/student.csv')
IQ_data = pd.read_csv("data/IQ.csv").to_dict('records')
PISA_data = pd.read_csv("data/PISA.csv").to_dict('records')
Literacy_data = pd.read_csv("data/Education.csv").to_dict('records')

@app.route("/")
def home():
    return render_template("home.html")

@app.route('/data/<filename>')
def serve_data(filename):
    return send_from_directory('data', filename)

@app.route("/api/world-data")
def world_data():
    data_type = request.args.get("type", "iq")  # default to IQ
    filename = ""
    
    if data_type == "iq":
        filename = "IQ.csv"
    elif data_type == "pisa":
        filename = "PISA.csv"
    elif data_type == "literacy":
        filename = "Education.csv"
    
    if not os.path.exists(f"data/{filename}"):
        return jsonify({"error": f"{filename} not found"}), 404

    df = pd.read_csv(f"data/{filename}")
    return jsonify(df.to_dict(orient="records"))

@app.route('/data')
def data():
    return render_template('data.html')

@app.route('/api/list-merged-files')
def list_merged_files():
    """Returns a list of all files in the data directory, merging related World Bank files"""
    data_dir = 'data'
    files = []
    
    # Track file groups for merging
    file_groups = {}
    
    # Scan all files in the data directory
    for filename in os.listdir(data_dir):
        file_path = os.path.join(data_dir, filename)
        
        # Skip directories and hidden files
        if os.path.isdir(file_path) or filename.startswith('.'):
            continue
        
        # Get file metadata
        stats = os.stat(file_path)
        last_modified = datetime.fromtimestamp(stats.st_mtime).strftime('%Y-%m-%d')
        file_size = stats.st_size
        
        # Check if this is a World Bank file
        # World Bank files often follow patterns like API_SE.PRM.UNER.MA_DS2_en_csv_v2_93817
        if filename.startswith('API_'):
            # Try to identify base name
            # Extract the core part (e.g., SE.PRM.UNER.MA_DS2_en_csv_v2_93817)
            match = re.match(r'API_([^_]+)', filename)
            if match:
                base_indicator = match.group(1)
                
                # Group related files
                if base_indicator not in file_groups:
                    file_groups[base_indicator] = []
                
                file_groups[base_indicator].append({
                    'name': filename,
                    'path': file_path,
                    'size': file_size,
                    'lastModified': last_modified
                })
        
        # Get row count for CSV files
        row_count = None
        if filename.endswith('.csv'):
            try:
                with open(file_path, 'r') as f:
                    # Count lines and subtract header
                    row_count = sum(1 for line in f) - 1
            except Exception as e:
                print(f"Error counting rows in {filename}: {e}")
        
        # Add file to list
        files.append({
            'name': filename,
            'path': file_path,
            'size': file_size,
            'lastModified': last_modified,
            'rowCount': row_count,
            'isMerged': False
        })
    
    # Create merged files
    merged_files = []
    for base_indicator, group in file_groups.items():
        if len(group) > 1:
            # This is a group of related files
            filenames = [f['name'] for f in group]
            
            # Create a merged file entry
            merged_name = f"Merged_API_{base_indicator}.csv"
            
            # Get the most recent last modified date
            last_modified = max(f['lastModified'] for f in group)
            
            # Get the row count from the data file if available
            row_count = None
            for f in group:
                if 'Data' in f['name'] and f.get('rowCount'):
                    row_count = f['rowCount']
                    break
            
            merged_files.append({
                'name': merged_name,
                'size': sum(f['size'] for f in group),
                'lastModified': last_modified,
                'rowCount': row_count,
                'isMerged': True,
                'mergedFrom': filenames,
                'description': get_indicator_name(base_indicator)
            })
    
    # Add merged files to the beginning of the list
    files = merged_files + files
    
    return jsonify(files)


@app.route('/api/data-file/<filename>')
def get_data_file(filename):
    """Returns the contents of a specific CSV file, handling merged files if needed"""
    try:
        # Check if this is a merged file request
        if filename.startswith('Merged_API_'):
            # Extract the indicator code
            indicator_match = re.match(r'Merged_API_([^\.]+)', filename)
            if indicator_match:
                indicator = indicator_match.group(1)
                return get_merged_data(indicator)
        
        # Regular file handling
        file_path = os.path.join('data', filename)
        df = pd.read_csv(file_path)
        
        # Convert NaN values to None for JSON serialization
        df = df.where(pd.notnull(df), None)
        
        return jsonify({
            'headers': df.columns.tolist(),
            'data': df.values.tolist()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 404

def get_merged_data(indicator):
    """Merges related World Bank files for an indicator"""
    data_dir = 'data'
    
    # Find all related files
    data_file = None
    metadata_file = None
    footnote_file = None
    
    # Look for files matching the pattern
    for filename in os.listdir(data_dir):
        if filename.startswith(f'API_{indicator}'):
            file_path = os.path.join(data_dir, filename)
            
            # Categorize file type
            if 'Metadata' in filename:
                metadata_file = file_path
            elif 'Footnote' in filename:
                footnote_file = file_path
            else:
                data_file = file_path
    
    # Start with the data file as the base
    if not data_file:
        return jsonify({'error': 'Data file not found'}), 404
    
    df = pd.read_csv(data_file)
    
    # Add metadata if available
    metadata = {}
    if metadata_file:
        try:
            meta_df = pd.read_csv(metadata_file)
            
            # Convert metadata to dictionary
            for _, row in meta_df.iterrows():
                if 'Indicator Name' in row and 'Indicator Code' in row:
                    indicator_code = row['Indicator Code']
                    indicator_name = row['Indicator Name']
                    metadata[indicator_code] = indicator_name
            
            # Add indicator name as a column if we have it
            if indicator in metadata:
                df['Indicator Name'] = metadata[indicator]
        except Exception as e:
            print(f"Error processing metadata: {e}")
    
    # Add footnotes if available
    if footnote_file:
        try:
            footnote_df = pd.read_csv(footnote_file)
            
            # We could merge footnotes, but for simplicity, we'll just append them
            if not df.empty and not footnote_df.empty:
                # Create a new 'Footnotes' column in the data
                common_columns = set(df.columns) & set(footnote_df.columns)
                if common_columns:
                    # Create a mapping for footnotes
                    footnote_map = {}
                    
                    # Use common columns to identify matching rows
                    for _, row in footnote_df.iterrows():
                        key = tuple(row[col] for col in common_columns)
                        footnote = row.get('Footnote', '')
                        if footnote:
                            footnote_map[key] = footnote
                    
                    # Create a new column for footnotes
                    df['Footnote'] = df.apply(
                        lambda row: footnote_map.get(tuple(row[col] for col in common_columns), ''),
                        axis=1
                    )
        except Exception as e:
            print(f"Error processing footnotes: {e}")
    
    # Convert NaN values to None for JSON serialization
    df = df.where(pd.notnull(df), None)
    
    return jsonify({
        'headers': df.columns.tolist(),
        'data': df.values.tolist()
    })

def get_indicator_name(indicator_code):
    """Returns a human-readable name for a World Bank indicator code"""
    indicator_names = {
        'SE.PRM.UNER.MA': 'Primary Education Enrollment (Male)',
        'SE.PRM.UNER.FE': 'Primary Education Enrollment (Female)',
        'SE.XPD.PRIM.PC.ZS': 'Government Expenditure on Primary Education',
        'SE.XPD.TOTL.GD.ZS': 'Government Expenditure on Education (% of GDP)',
        # Add more mappings as needed
    }
    
    return indicator_names.get(indicator_code, f'World Bank Indicator: {indicator_code}')
    
@app.route('/api/list-files')
def list_files():
    """Returns a list of all files in the data directory with metadata"""
    data_dir = 'data'
    files = []
    
    # Check if there's a metadata file for additional info
    metadata_file = os.path.join(data_dir, 'metadata.json')
    metadata = {}
    if os.path.exists(metadata_file):
        try:
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
        except Exception as e:
            print(f"Error loading metadata file: {e}")
    
    # Scan all files in the data directory
    for filename in os.listdir(data_dir):
        file_path = os.path.join(data_dir, filename)
        
        # Skip directories and hidden files
        if os.path.isdir(file_path) or filename.startswith('.') or filename == 'metadata.json':
            continue
        
        # Get file metadata
        stats = os.stat(file_path)
        last_modified = datetime.fromtimestamp(stats.st_mtime).strftime('%Y-%m-%d')
        file_size = stats.st_size
        
        # Get file type
        file_type = mimetypes.guess_type(file_path)[0]
        
        # Get description from metadata if available
        description = None
        if filename in metadata:
            description = metadata[filename].get('description')
        
        # If not in metadata, generate a description from filename
        if not description:
            description = filename.replace('.csv', '').replace('_', ' ').replace('-', ' ')
            # Extract meaningful part from API filenames
            if description.startswith('API '):
                parts = description.split(' ')
                if len(parts) > 1:
                    description = parts[1].replace('.', ' ')
            
            # Capitalize each word
            description = ' '.join(word.capitalize() for word in description.split())
        
        # Create file info object
        file_info = {
            'name': filename,
            'path': file_path,
            'size': file_size,
            'lastModified': last_modified,
            'type': file_type,
            'description': description
        }
        
        # Add any additional metadata
        if filename in metadata:
            file_info.update(metadata[filename])
        
        files.append(file_info)
    
    # Add any external links from metadata
    if 'links' in metadata:
        for link in metadata['links']:
            files.append({
                'name': link.get('name', 'External Link'),
                'type': 'link',
                'url': link.get('url', '#'),
                'description': link.get('description', 'External Resource'),
                'lastModified': link.get('lastModified', datetime.now().strftime('%Y-%m-%d'))
            })
    
    return jsonify(files)

@app.route('/visualization')
def visualization():
    return render_template('visualization.html')

@app.route('/akun')
def akun():
    return render_template('akun.html')

if __name__ == "__main__":
    app.run(debug=True)