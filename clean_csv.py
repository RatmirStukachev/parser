import csv

urls = set()
unique_rows = []

with open('eco_products.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    for row in reader:
        url = row['url']
        if url not in urls:
            urls.add(url)
            unique_rows.append(row)

with open('eco_products.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(unique_rows)

print(f"Cleaned CSV. Total unique rows: {len(unique_rows)}")
