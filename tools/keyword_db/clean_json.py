import json
import re
from pathlib import Path

def clean_text(text):
    """Clean up text content in the JSON."""
    if not isinstance(text, str):
        return text
    
    # Fix common HTML entities
    text = text.replace('&copy;', '©')
    text = text.replace('Â©', '©')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&amp;', '&')
    text = text.replace('&quot;', '"')
    
    # Remove MathType artifacts
    text = re.sub(r'MathType@.*?@', '', text)
    
    # Clean up whitespace
    text = ' '.join(text.split())
    
    return text

def clean_json_data(data):
    """Recursively clean JSON data."""
    if isinstance(data, dict):
        return {k: clean_json_data(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [clean_json_data(item) for item in data]
    elif isinstance(data, str):
        return clean_text(data)
    else:
        return data

def main():
    input_file = Path(__file__).resolve().parents[2] / 'data' / 'archiv' / 'lsdyna_keywords.json'
    output_file = input_file.with_name('lsdyna_keywords_cleaned.json')
    
    # Read the original JSON file
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Clean the data
    cleaned_data = clean_json_data(data)
    
    # Write the cleaned data back to a new file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(cleaned_data, f, indent=2, ensure_ascii=False)
    
    print(f"Cleaned JSON saved to: {output_file}")

if __name__ == "__main__":
    main()
