import sqlite3
import xml.etree.ElementTree as ET
from html import unescape
from html.parser import HTMLParser
import re
import inflect
import pyinflect
import spacy

# Load the spaCy model
nlp = spacy.load("en_core_web_sm")

class HTMLCleaner(HTMLParser):
    def __init__(self):
        super().__init__()
        self.cleaned_html = ""
    
    def handle_starttag(self, tag, attrs):
        self.cleaned_html += f"<{tag}"
        for attr, value in attrs:
            self.cleaned_html += f' {attr}="{value}"'
        self.cleaned_html += ">"
    
    def handle_endtag(self, tag):
        self.cleaned_html += f"</{tag}>"
    
    def handle_data(self, data):
        self.cleaned_html += data
    
    def handle_entityref(self, name):
        self.cleaned_html += f"&{name};"
    
    def handle_charref(self, name):
        self.cleaned_html += f"&#{name};"
    
    def handle_startendtag(self, tag, attrs):
        self.cleaned_html += f"<{tag}"
        for attr, value in attrs:
            self.cleaned_html += f' {attr}="{value}"'
        self.cleaned_html += " />"

def clean_html(html_content):
    # Replace <br> with <br />
    html_content = html_content.replace("<br>", "<br />").replace("&", "&amp;")
    cleaner = HTMLCleaner()
    cleaner.feed(html_content)
    return cleaner.cleaned_html

def preprocess_html(html_content):
    # Unescape HTML content first
    html_content = unescape(html_content)
    
    # Replace <br> with <br /> and sanitize & characters
    html_content = re.sub(r'<br(?!\s*/)>', '<br />', html_content)
    html_content = re.sub(r'&(?![a-zA-Z]+;|#[0-9]+;|#x[0-9a-fA-F]+;)', '&amp;', html_content)
    
    # Escape standalone < and > characters by splitting on valid tags and replacing only outside of tags
    parts = re.split(r'(<[^>]+>)', html_content)
    for i, part in enumerate(parts):
        if not part.startswith('<') and not part.endswith('>'):
            part = part.replace('<', '&lt;').replace('>', '&gt;')
        parts[i] = part
    
    html_content = ''.join(parts)
    
    return html_content

def log_error_details(definition, error):
    position = error.position
    error_char = definition[max(0, position[1]-20):position[1]+20]  # Show 20 characters around the error position for context
    print(f"Error in entry at _id={_id} around: '{error_char}' (position {position})")
    print(f"Complete definition: {definition}")

def generate_word_variations(word):
    p = inflect.engine()
    variations = [word, p.plural(word)]
    
    if word == 'go':
        variations.extend(['went', 'gone'])
    else:
        # Using pyinflect for verb conjugations
        doc = nlp(word)
        for token in doc:
            variations.extend([
                token._.inflect("VBG"),  # Present participle
                token._.inflect("VBD"),  # Past tense
                token._.inflect("VBN")   # Past participle
            ])
    
    # Filter out None values and return unique variations
    return set(filter(None, variations))

# Connect to the SQLite database
conn = sqlite3.connect('dictionary.db')

cursor = conn.cursor()

# Query to select the specific columns
cursor.execute("SELECT _id, word, title, definition FROM dictionary")
rows = cursor.fetchall()

# Create the root element for the XML
root = ET.Element('d:dictionary', attrib={
    'xmlns': 'http://www.w3.org/1999/xhtml',
    'xmlns:d': 'http://www.apple.com/DTDs/DictionaryService-1.0.rng'
})

# Add a newline after the root element for readability
root.text = "\n"

# Iterate over the rows and create XML structure
for row in rows:
    _id, word, title, definition = row
    entry_id = f"{word.lower()}_{_id}"

    entry = ET.SubElement(root, 'd:entry', attrib={'id': entry_id, 'd:title': word})
    
    # Generate variations and create d:index elements
    variations = generate_word_variations(word)
    for variation in variations:
        index = ET.SubElement(entry, 'd:index', attrib={'d:value': variation.lower()})
    
    priority = ET.SubElement(entry, 'div', attrib={'d:priority': str(_id)})
    h1 = ET.SubElement(priority, 'h1')

    syntax = ET.SubElement(entry, 'span', attrib={'class': 'syntax'})
    span = ET.SubElement(syntax, 'span', attrib={'d:pr': 'US'})
    span.text = ''

    content = ET.SubElement(entry, 'span')
    # Wrap the definition content in a single root element and clean it
    try:
        preprocessed_definition = preprocess_html(definition)
        cleaned_definition = clean_html(preprocessed_definition)
        wrapped_definition = f"<root>{cleaned_definition}</root>"
        content.extend(ET.fromstring(wrapped_definition))
    except ET.ParseError as e:
        log_error_details(definition, e)
        
        print(f"Skipping entry with _id={_id} due to malformed HTML.")
        root.remove(entry)
        continue

    # Add a newline after each entry for readability
    entry.tail = "\n"

# Convert the XML tree to a string
xml_string = ET.tostring(root, encoding='utf-8', method='xml').decode()

# Add the XML declaration manually
xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>\n'

# Save the XML string to a file
with open('output.xml', 'w', encoding='utf-8') as f:
    f.write(xml_declaration + xml_string)

# Close the database connection
conn.close()
