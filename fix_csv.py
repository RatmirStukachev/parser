import csv

with open('eco_products.csv', 'r', encoding='utf-8') as f:
    # Read raw lines
    lines = f.readlines()

if not lines[0].startswith('title'):
    lines.insert(0, 'title,vendor_code,price,description,characteristics,image_url,url\n')

with open('eco_products.csv', 'w', encoding='utf-8') as f:
    f.writelines(lines)
