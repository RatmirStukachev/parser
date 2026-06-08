import requests
from bs4 import BeautifulSoup
import csv
import re
import time
import urllib.parse
import os

BASE_URL = "https://tools.by"
BRAND_URL = "https://tools.by/brands/eco"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7"
}

def get_soup(url, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=HEADERS, timeout=15)
            response.raise_for_status()
            return BeautifulSoup(response.text, 'html.parser'), response.text
        except requests.exceptions.RequestException as e:
            print(f"Error fetching {url}: {e}. Retrying {attempt + 1}/{max_retries}...")
            time.sleep(2)
    return None, None

def get_category_links():
    soup, _ = get_soup(BRAND_URL)
    if not soup:
        return []

    category_links = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        if '/catalog/' in href and 'brand_id' in href:
            if not href.startswith('http'):
                href = urllib.parse.urljoin(BASE_URL, href)
            category_links.append(href)

    return list(set(category_links))

def get_product_links_from_category(category_url):
    product_links = set()
    page = 1

    while True:
        if '?' in category_url:
            if 'page=' in category_url:
                url = re.sub(r'page=\d+', f'page={page}', category_url)
            else:
                url = f"{category_url}&page={page}"
        else:
            url = f"{category_url}?page={page}"

        soup, _ = get_soup(url)
        if not soup:
            break

        page_product_links = []
        for a in soup.find_all('a', href=True):
            if '/product/' in a['href']:
                href = a['href']
                if not href.startswith('http'):
                    href = urllib.parse.urljoin(BASE_URL, href)
                if '#' not in href:
                    page_product_links.append(href)

        page_product_links = list(set(page_product_links))

        if not page_product_links:
            break

        initial_count = len(product_links)
        product_links.update(page_product_links)

        if len(product_links) == initial_count:
             break

        has_next = False
        for p in soup.find_all('a', class_=re.compile(r'page-link|pagination')):
            if p.text.strip() == str(page + 1) or 'next' in p.text.lower() or '»' in p.text:
                has_next = True
                break

        page += 1
        time.sleep(0.5)

    return list(product_links)

def parse_product(url):
    soup, html_text = get_soup(url)
    if not soup:
        return None

    product_data = {'url': url}

    # Title
    title_el = soup.find('h1')
    product_data['title'] = title_el.text.strip() if title_el else ""

    # Vendor Code
    vendor_code = ""
    vendor_el = soup.find('div', class_='product__vendor-code')
    if vendor_el:
        vendor_code = vendor_el.text.replace('Арт.:', '').strip()
    else:
        vendor_match = re.search(r'Арт\.:\s*([^\s<]+)', html_text)
        if vendor_match:
            vendor_code = vendor_match.group(1)

    product_data['vendor_code'] = vendor_code

    # Price
    price = ""
    price_el = soup.find('span', class_='price', attrs={'data-price': True})
    if price_el:
        price = price_el.text.strip()
    product_data['price'] = price

    # Image
    img_url = ""
    meta_img = soup.find('meta', property='og:image')
    if meta_img:
        img_url = meta_img.get('content')
    else:
        img_el = soup.find('img', class_=re.compile(r'hover-and-scale|product'))
        if img_el and img_el.get('src'):
            img_url = img_el.get('src')
            if not img_url.startswith('http'):
                img_url = urllib.parse.urljoin(BASE_URL, img_url)
    product_data['image_url'] = img_url

    # Description
    desc_section = soup.find('div', class_=re.compile("description", re.I)) or soup.find(id=re.compile("description", re.I))
    product_data['description'] = desc_section.text.strip().replace('\n', ' | ') if desc_section else ""
    product_data['description'] = re.sub(r'\s+', ' ', product_data['description']).strip()

    # Characteristics
    characteristics = {}
    char_section = soup.find('div', class_=re.compile("characteristics", re.I)) or soup.find('table', class_=re.compile("char", re.I))

    if char_section:
        rows = char_section.find_all('tr')
        for row in rows:
            cols = row.find_all(['th', 'td'])
            if len(cols) >= 2:
                key = cols[0].text.strip()
                val = cols[1].text.strip()
                if key and val:
                    characteristics[key] = val

    char_str = "; ".join([f"{k}: {v}" for k, v in characteristics.items()])
    product_data['characteristics'] = char_str

    # Check characteristics for vendor code if still empty
    if not product_data['vendor_code']:
        for k, v in characteristics.items():
            if 'артикул' in k.lower() or 'код' in k.lower():
                product_data['vendor_code'] = v
                break

    return product_data

def main():
    print("Fetching category links...")
    category_links = get_category_links()
    print(f"Found {len(category_links)} categories.")

    output_file = 'eco_products.csv'
    fieldnames = ['title', 'vendor_code', 'price', 'description', 'characteristics', 'image_url', 'url']

    existing_urls = set()
    if os.path.exists(output_file):
        with open(output_file, 'r', encoding='utf-8') as f:
            try:
                reader = csv.DictReader(f)
                for row in reader:
                    existing_urls.add(row['url'])
            except:
                pass

    mode = 'a' if os.path.exists(output_file) else 'w'

    # We will write directly so if it timeouts we keep data
    with open(output_file, mode, newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if mode == 'w':
            writer.writeheader()

        all_product_links = set()
        for i, cat_url in enumerate(category_links):
            print(f"[{i+1}/{len(category_links)}] Scraping category: {cat_url}")
            product_links = get_product_links_from_category(cat_url)
            all_product_links.update([link for link in product_links if link not in existing_urls])

        all_product_links = list(all_product_links)
        print(f"\nTotal new unique products to scrape: {len(all_product_links)}")

        for i, prod_url in enumerate(all_product_links):
            data = parse_product(prod_url)
            if data:
                writer.writerow(data)
                f.flush()
            time.sleep(0.1)

    print("\nScraping complete. Data saved to eco_products.csv")

if __name__ == "__main__":
    main()
