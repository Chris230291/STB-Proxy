import stb
import json

url = "http://techking.uk:2095/portal.php"
mac = "00:1A:79:36:29:D0"
proxy = "http://10.0.1.200:8086"

token = stb.getToken(url, mac, proxy)

#with open('json_data.json', 'w') as outfile:
#    json.dump(stb.getVods(url, mac, token, proxy), outfile, indent=4)

# with open('json_data.json') as json_file:
#     data = json.load(json_file)

# for vod in data:
#     if str(vod["id"]) == "215609":
#         print (vod)

# print(stb.test(url, mac, token, proxy))

l=[]
if type(l) == list:
    print("y")