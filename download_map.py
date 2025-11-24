import requests
import os

urls = [
    "https://raw.githubusercontent.com/djaiss/mapsicon/master/all/lt/vector.svg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/7/72/Map_of_Lithuania_2.svg/1280px-Map_of_Lithuania_2.svg.png",
    "https://restcountries.com/v3.1/alpha/ltu" # To get flag/map url
]
output_path = "webapp/map_lt.svg" # Saving as SVG
headers = {'User-Agent': 'Mozilla/5.0'}

for url in urls:
    try:
        print(f"Trying {url}...")
        response = requests.get(url, headers=headers, stream=True)
        if response.status_code == 200:
            with open(output_path, 'wb') as f:
                f.write(response.content)
            print(f"Successfully downloaded to {output_path}")
            break
        else:
            print(f"Failed: {response.status_code}")
    except Exception as e:
        print(f"Error downloading {url}: {e}")
