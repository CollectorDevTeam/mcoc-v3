from selenium import webdriver

driver = webdriver.Chrome()
driver.get("https://auntm.ai/champions")

response = requests.get(url+"/home/index.html")
print(response)
# Parse the HTML response
soup = BeautifulSoup(response.text, "html.parser")

# Find the script tag with the main.*.chunk.js file
script_tag = soup.find("script", src=lambda s: s and "main" in s and "chunk.js" in s)


# Get the array data from the webpage
array_data = driver.execute_script("return webpackJsonauntm.ai-web")

# Export the array data to Python
print(array_data)
