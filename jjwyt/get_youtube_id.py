# Get youtube id
#http://youtu.be/5Y6HSHwhVlY
#http://www.youtube.com/embed/5Y6HSHwhVlY?rel=0
#http://www.youtube.com/watch?v=ZFqlHhCNBOI
import re

regex = re.compile(r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/(watch\?v=|embed/|v/|.+\?v=)?(?P<id>[A-Za-z0-9\-=_]{11})')

# match = regex.match(self.youtube_url)

def regexyt(youtubeid:str):
    
    return regex.match(youtubeid)

# if not match:
#     print('no match')
# print(match.group('id'))

# Online Test: https://pythex.org/?regex=(https%3F%3A%2F%2F)%3F(www%5C.)%3F(youtube%7Cyoutu%7Cyoutube-nocookie)%5C.(com%7Cbe)%2F(watch%5C%3Fv%3D%7Cembed%2F%7Cv%2F%7C.%2B%5C%3Fv%3D)%3F(%3FP%3Cid%3E%5BA-Za-z0-9%5C-%3D_%5D%7B11%7D)&test_string=http%3A%2F%2Fyoutu.be%2F5Y6HSHwhVlY%0Ahttp%3A%2F%2Fwww.youtube.com%2Fembed%2F5Y6HSHwhVlY%3Frel%3D0%0Ahttp%3A%2F%2Fwww.youtube.com%2Fwatch%3Fv%3DZFqlHhCNBOI&ignorecase=0&multiline=0&do