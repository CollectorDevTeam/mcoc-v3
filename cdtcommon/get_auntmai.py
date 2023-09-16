import json
import requests
from bs4 import BeautifulSoup
import discord
import re
import js2py
from os.path import exists

url = "https://auntm.ai"


# Make an HTTP GET request to the URL
response = requests.get(url+"/home/index.html")
print(response)
# Parse the HTML response
soup = BeautifulSoup(response.text, "html.parser")

# Find the script tag with the main.*.chunk.js file
script_tag = soup.find("script", src=lambda s: s and "main" in s and "chunk.js" in s)

if script_tag:
    # Extract the JavaScript file URL
    js_file_url = url + script_tag["src"]
    save_file_path = "{}".format(script_tag["src"])
    save_file_path = re.sub('/static/js/', '', save_file_path)
    if not(exists(save_file_path)):
        response = requests.get(js_file_url)
        if response.status_code==200:
            with open(save_file_path, "wb") as file:
                file.write(response.content)
            print("File downloaded and saved successfully")
    elif exists(save_file_path):
        print("File already cached.")

    # if exists(save_file_path):
    #     print("Attempting to convert js")



else:
    print("JavaScript file not found")



