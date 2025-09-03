# convert_to_utf8.py
import codecs

with codecs.open("db.json", "r", encoding="latin1") as f:  # use 'latin1' or 'cp1252'
    text = f.read()

with open("db_utf8.json", "w", encoding="utf-8") as f:
    f.write(text)

print("Converted to db_utf8.json in UTF-8!")
