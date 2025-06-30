import os
import json
import csv
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

# ... inside the loop



# === CONFIGURATION ===
json_file_path = "/Users/anri/PycharmProjects/pythonProject2/hokusai_painting_links.json"  # <- Fill this with your JSON path
output_folder = "hokusai_output"
image_folder = os.path.join(output_folder, "images")
csv_path = os.path.join(output_folder, "metadata.csv")

# === SETUP ===
os.makedirs(image_folder, exist_ok=True)

# === READ JSON ===
with open(json_file_path, 'r') as f:
    data = json.load(f)
    links = data['links']

# === FIELDNAMES ===
fieldnames = [
    'Index', 'Image Filename', 'Title', 'Creator', 'Date Created',
    'Physical Dimensions', 'Medium', 'Object Classification', 'Full Title',
    'Curatorial Area', 'Credit Line', 'Chronology',
    'Artwork Accession Number', 'Page URL'
]

# === START PROCESSING ===
with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()

    for index, url in enumerate(links, start=1):
        print(f"[{index}/{len(links)}] Processing {url}")
        try:
            res = requests.get(url, timeout=10)
            res.raise_for_status()
            soup = BeautifulSoup(res.text, 'html.parser')

            metadata = {key: '' for key in fieldnames}
            metadata['Index'] = index
            metadata['Page URL'] = url

            # === Get Image URL from <meta property="og:image">
            meta_img = soup.find('meta', property='og:image')
            if meta_img and meta_img.get('content'):
                image_url = meta_img['content']
                parsed_url = urlparse(image_url)
                filename_ext = os.path.basename(parsed_url.path) or f"{index:04d}.jpg"
                image_filename = f"{index:04d}_{filename_ext.split('=')[0]}.jpg"
                metadata['Image Filename'] = image_filename

                # === Download image
                img_data = requests.get(image_url).content
                with open(os.path.join(image_folder, image_filename), 'wb') as f_img:
                    f_img.write(img_data)
            else:
                print("⚠️ Image not found.")

            # === Parse metadata from <ul> list ===
            ul = soup.find('ul')
            if ul:
                for li in ul.find_all('li'):
                    key_elem = li.find('span')
                    if key_elem:
                        key = key_elem.text.replace(':', '').strip()
                        value = li.get_text().replace(key_elem.text, '').strip()
                        if key in fieldnames:
                            metadata[key] = value

            writer.writerow(metadata)
            time.sleep(1)  # Be kind to the server
        except Exception as e:
            print(f"❌ Error processing {url}: {e}")

print("✅ All done.")
