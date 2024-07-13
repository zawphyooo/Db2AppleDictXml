import sqlite3
import xml.etree.ElementTree as ET
from html import unescape
from html.parser import HTMLParser

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
    html_content = html_content.replace("<br>", "<br />")
    cleaner = HTMLCleaner()
    cleaner.feed(html_content)
    return cleaner.cleaned_html

# Connect to the SQLite database
# This data base is from https://github.com/soeminnminn/EngMyanDictionary/blob/master/app/src/main/assets/database/dictionary.db
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
    index = ET.SubElement(entry, 'd:index', attrib={'d:value': word.lower()})
    priority = ET.SubElement(entry, 'div', attrib={'d:priority': str(_id)})
    h1 = ET.SubElement(priority, 'h1')
    h1.text = word

    syntax = ET.SubElement(entry, 'span', attrib={'class': 'syntax'})
    span = ET.SubElement(syntax, 'span', attrib={'d:pr': 'US'})
    span.text = ''

    content = ET.SubElement(entry, 'div')
    # Wrap the definition content in a single root element and clean it
    try:
        cleaned_definition = clean_html(unescape(definition))
        wrapped_definition = f"<root>{cleaned_definition}</root>"
        content.extend(ET.fromstring(wrapped_definition))
    except ET.ParseError as e:
        print(f"Skipping entry with _id={_id} due to malformed HTML. Error: {e}")
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
