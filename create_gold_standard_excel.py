#!/usr/bin/env python3
"""
Script to convert Q&A JSON files to Excel format for human review and analysis.
Creates EDBOTGoldstard.xls with columns for accuracy, precision, and recall analysis.
"""

import glob
import json
import os

import pandas as pd


def load_qa_files(base_dir):
    """Load all Q&A JSON files from the ground_truth_qa directory."""
    qa_data = []
    
    # Find all JSON files in subdirectories
    pattern = os.path.join(base_dir, "**", "*.json")
    json_files = glob.glob(pattern, recursive=True)
    
    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Extract category from file path
            rel_path = os.path.relpath(json_file, base_dir)
            category = rel_path.split(os.sep)[0]  # guidelines/protocols/reference/training
            
            # Handle both list of objects and single object formats
            if isinstance(data, list):
                for item in data:
                    item['category'] = category
                    item['source_file'] = os.path.basename(json_file)
                    qa_data.extend([item] if isinstance(item, dict) else [])
            elif isinstance(data, dict):
                data['category'] = category  
                data['source_file'] = os.path.basename(json_file)
                qa_data.append(data)
                
        except Exception as e:
            print(f"Error processing {json_file}: {e}")
            continue
    
    return qa_data

def create_excel_file(qa_data, output_path):
    """Create Excel file with analysis columns for human review."""
    
    # Create DataFrame
    df_data = []
    
    for i, item in enumerate(qa_data, 1):
        row = {
            'ID': i,
            'Category': item.get('category', 'Unknown'),
            'Source_File': item.get('source_file', 'Unknown'),
            'Source_Document': item.get('source', 'Unknown'),
            'Query_Type': item.get('query_type', 'Unknown'),
            'Question': item.get('question', ''),
            'Expert_Answer': item.get('answer', ''),
            
            # Columns for human analysis
            'Chatbot_Response': '',  # To be filled by evaluator
            'Accuracy_Score': '',   # Percentage match (0-100%)
            'Accuracy_Notes': '',   # Notes on accuracy assessment
            
            # RAG Analysis Columns  
            'Retrieved_Documents': '',  # List of docs retrieved by RAG
            'Relevant_Retrieved': '',   # Count of relevant docs retrieved
            'Total_Retrieved': '',      # Total docs retrieved
            'Precision_Score': '',      # Relevant_Retrieved / Total_Retrieved (0-100%)
            'Precision_Notes': '',      # Notes on precision assessment
            
            'Total_Relevant_Available': '',  # Total relevant docs in knowledge base
            'Recall_Score': '',             # Relevant_Retrieved / Total_Relevant_Available (0-100%)  
            'Recall_Notes': '',             # Notes on recall assessment
            
            # Overall Assessment
            'Overall_Rating': '',           # Excellent/Good/Fair/Poor
            'Issues_Identified': '',       # Any problems found
            'Reviewer_Notes': '',          # General notes
            'Review_Date': '',             # Date of review
            'Reviewer_Name': ''            # Name of reviewer
        }
        
        df_data.append(row)
    
    df = pd.DataFrame(df_data)
    
    # Save to Excel with formatting
    with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='QA_Analysis', index=False)
        
        # Get workbook and worksheet objects
        workbook = writer.book
        worksheet = writer.sheets['QA_Analysis']
        
        # Define formats
        header_format = workbook.add_format({
            'bold': True,
            'text_wrap': True,
            'valign': 'top',
            'bg_color': '#4472C4',
            'font_color': 'white',
            'border': 1
        })
        
        cell_format = workbook.add_format({
            'text_wrap': True,
            'valign': 'top',
            'border': 1
        })
        
        # Set column widths and formats
        col_widths = {
            'A': 5,   # ID
            'B': 12,  # Category  
            'C': 20,  # Source_File
            'D': 25,  # Source_Document
            'E': 15,  # Query_Type
            'F': 40,  # Question
            'G': 50,  # Expert_Answer
            'H': 50,  # Chatbot_Response
            'I': 12,  # Accuracy_Score
            'J': 30,  # Accuracy_Notes
            'K': 30,  # Retrieved_Documents
            'L': 12,  # Relevant_Retrieved
            'M': 12,  # Total_Retrieved  
            'N': 12,  # Precision_Score
            'O': 30,  # Precision_Notes
            'P': 15,  # Total_Relevant_Available
            'Q': 12,  # Recall_Score
            'R': 30,  # Recall_Notes
            'S': 15,  # Overall_Rating
            'T': 30,  # Issues_Identified
            'U': 40,  # Reviewer_Notes
            'V': 12,  # Review_Date
            'W': 15   # Reviewer_Name
        }
        
        for col, width in col_widths.items():
            worksheet.set_column(f'{col}:{col}', width, cell_format)
        
        # Format header row
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_format)
        
        # Set row height for better readability
        worksheet.set_default_row(30)
        
        # Freeze panes at row 1 and column F (after basic info)
        worksheet.freeze_panes(1, 5)

def main():
    base_dir = "/mnt/d/Dev/EDbotv8/ground_truth_qa"
    output_dir = "/mnt/d/Dev/EDbotv8/IRR Items"
    output_file = os.path.join(output_dir, "EDBOTGoldstard.xlsx")
    
    print("Loading Q&A files...")
    qa_data = load_qa_files(base_dir)
    
    print(f"Found {len(qa_data)} Q&A pairs")
    
    # Print summary by category
    categories = {}
    for item in qa_data:
        cat = item.get('category', 'Unknown')
        categories[cat] = categories.get(cat, 0) + 1
    
    print("\nQ&A pairs by category:")
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count}")
    
    print(f"\nCreating Excel file: {output_file}")
    create_excel_file(qa_data, output_file)
    
    print("✅ Excel file created successfully!")
    print(f"\nFile location: {output_file}")
    print(f"Total Q&A pairs: {len(qa_data)}")
    
    print("\nAnalysis targets:")
    print("- Accuracy: >85% (chatbot response matches expert consensus)")  
    print("- Precision: >80% (relevant docs / total retrieved docs)")
    print("- Recall: >75% (relevant docs retrieved / total relevant available)")

if __name__ == "__main__":
    main()