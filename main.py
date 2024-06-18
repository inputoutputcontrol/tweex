import requests
import sys
import json

def scrape(url):
    baseurl = f"https://publish.x.com/oembed?url={url}"
    response = requests.get(baseurl)
    if response.status_code == 200:
        data = response.json()
        formatted = json.dumps(data, indent=4)
        print(formatted)
    else:
        print(f"{response.status_code}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("py script.py <url>")
        sys.exit(1)
    url = sys.argv[1]
    scrape(url)
