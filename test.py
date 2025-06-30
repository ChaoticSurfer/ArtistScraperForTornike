from bs4 import BeautifulSoup
import requests
html = requests.get('https://artsandculture.google.com/asset/%C5%8Ckaru-and-kampei-outside-kamakura-castle-act-iii-from-the-play-ch%C5%ABshingura-katsushika-hokusai/zAE-bvKm5PAIjg')


soup = BeautifulSoup(html.text, "html.parser")
for i in soup.find_all('ul')[-1]:
    print(i.text.split(":",1))
