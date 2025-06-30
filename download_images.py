import os
import json
import csv
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

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
                print(f"📥 Downloading image: {image_filename}")
                img_data = requests.get(image_url).content
                with open(os.path.join(image_folder, image_filename), 'wb') as f_img:
                    f_img.write(img_data)
            else:
                print("⚠️ Image not found.")

            # === Parse metadata from the LAST <ul> list (this was the fix!) ===
            ul_elements = soup.find_all('ul')
            if ul_elements:
                # Get the last <ul> element which contains the metadata
                metadata_ul = ul_elements[-1]
                print(f"🔍 Found {len(ul_elements)} <ul> elements, using the last one for metadata")

                for li in metadata_ul.find_all('li'):
                    li_text = li.get_text()
                    # Split on first colon to separate key and value
                    if ':' in li_text:
                        key, value = li_text.split(':', 1)
                        key = key.strip()
                        value = value.strip()

                        # Map the key to our fieldnames if it exists
                        if key in fieldnames:
                            metadata[key] = value
                            print(f"  ✓ {key}: {value}")
            else:
                print("⚠️ No <ul> elements found for metadata")

            writer.writerow(metadata)
            print(f"✅ Completed processing item {index}")
            time.sleep(1)  # Be kind to the server

        except Exception as e:
            print(f"❌ Error processing {url}: {e}")
            # Still write a row with basic info even if there's an error
            error_metadata = {key: '' for key in fieldnames}
            error_metadata['Index'] = index
            error_metadata['Page URL'] = url
            writer.writerow(error_metadata)

print("✅ All done! Check your CSV file for the metadata.")