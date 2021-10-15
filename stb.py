import requests
from retrying import retry
from urllib.parse import urlparse


@retry(stop_max_attempt_number=6, wait_fixed=250)
def getToken(url, mac):
    cookies = {"mac": mac, "stb_lang": "en", "timezone": "Europe/London"}
    headers = {"User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C)"}
    response = requests.post(
        url + "?type=stb&action=handshake&JsHttpRequest=1-xml",
        cookies=cookies,
        headers=headers,
    )
    data = response.json()
    token = data["js"]["token"]
    if token:
        getProfile(url, mac, token)
        return token
    raise Exception("Error getting token")


@retry(stop_max_attempt_number=6, wait_fixed=250)
def getProfile(url, mac, token):
    try:
        cookies = {"mac": mac, "stb_lang": "en", "timezone": "Europe/London"}
        headers = {
            "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C)",
            "Authorization": "Bearer " + token,
        }
        response = requests.post(
            url + "?type=stb&action=get_profile&JsHttpRequest=1-xml",
            cookies=cookies,
            headers=headers,
        )
        data = response.json()
        if data:
            return data
    except:
        pass
    raise Exception("Error getting profile")


def getExpires(url, mac, token):
    try:
        cookies = {"mac": mac, "stb_lang": "en", "timezone": "Europe/London"}
        headers = {
            "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C)",
            "Authorization": "Bearer " + token,
        }
        response = requests.post(
            url + "?type=account_info&action=get_main_info&JsHttpRequest=1-xml",
            cookies=cookies,
            headers=headers,
        )
        data = response.json()
        expire = data["js"]["phone"]
        if expire:
            return expire
    except:
        pass
    return "Unkown"


@retry(stop_max_attempt_number=6, wait_fixed=250)
def getAllChannels(url, mac, token):
    try:
        cookies = {"mac": mac, "stb_lang": "en", "timezone": "Europe/London"}
        headers = {
            "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C)",
            "Authorization": "Bearer " + token,
        }
        response = requests.post(
            url
            + "?type=itv&action=get_all_channels&force_ch_link_check=&JsHttpRequest=1-xml",
            cookies=cookies,
            headers=headers,
        )
        channels = response.json()["js"]["data"]
        if channels:
            return channels
    except:
        pass
    raise Exception("Error getting channels")


@retry(stop_max_attempt_number=6, wait_fixed=250)
def getGenres(url, mac, token):
    try:
        cookies = {"mac": mac, "stb_lang": "en", "timezone": "Europe/London"}
        headers = {
            "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C)",
            "Authorization": "Bearer " + token,
        }
        response = requests.post(
            url + "?action=get_genres&type=itv&JsHttpRequest=1-xml",
            cookies=cookies,
            headers=headers,
        )
        genreData = response.json()["js"]
        genres = {}
        for i in genreData:
            gid = i["id"]
            name = i["title"]
            genres[gid] = name
        if genres:
            return genres
    except:
        pass
    raise Exception("Error getting genres")


def getShortEpg(channel, url, mac, token):
    try:
        cookies = {"mac": mac, "stb_lang": "en", "timezone": "Europe/London"}
        headers = {
            "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C)",
            "Authorization": "Bearer " + token,
        }
        response = requests.post(
            url
            + "?type=itv&action=get_short_epg&ch_id="
            + str(channel)
            + "&size=10&JsHttpRequest=1-xml",
            cookies=cookies,
            headers=headers,
        )
        epg = response.json()["js"]
        if epg:
            return epg
    except:
        pass
    return ""


@retry(stop_max_attempt_number=6, wait_fixed=250)
def getLink(url, mac, token, cmd):
    try:
        cookies = {"mac": mac, "stb_lang": "en", "timezone": "Europe/London"}
        headers = {
            "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C)",
            "Authorization": "Bearer " + token,
        }
        response = requests.post(
            url + "?type=itv&action=create_link&cmd=" + cmd + "&JsHttpRequest=1-xml",
            cookies=cookies,
            headers=headers,
        )
        data = response.json()
        link = data["js"]["cmd"].split()[-1]
        if link:
            return link
    except:
        pass
    raise Exception("Error getting link")


@retry(stop_max_attempt_number=6, wait_fixed=250)
def getLinkById(url, mac, token, channel):
    try:
        cookies = {"mac": mac, "stb_lang": "en", "timezone": "Europe/London"}
        headers = {
            "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C)",
            "Authorization": "Bearer " + token,
        }
        response = requests.post(
            url
            + "?type=itv&action=create_link&ch_id="
            + channel
            + "&JsHttpRequest=1-xml",
            cookies=cookies,
            headers=headers,
        )
        data = response.json()
        link = data["js"]["cmd"].split()[-1]
        if link:
            return link
    except:
        pass
    raise Exception("Error getting link")


def getUrl(url):
    url = urlparse(url).scheme + "://" + urlparse(url).netloc
    try:
        response = requests.get(url + "/c/")
    except:
        response = None
    if response:
        return url + "/portal.php"
    else:
        return url + "/stalker_portal/server/load.php"

@retry(stop_max_attempt_number=6, wait_fixed=250)
def getEpg(url, mac, token, period):
    try:
        cookies = {"mac": mac, "stb_lang": "en", "timezone": "Europe/London"}
        headers = {
            "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C)",
            "Authorization": "Bearer " + token,
        }
        response = requests.post(
            url + "?type=itv&action=get_epg_info&period=" + str(period) + "&JsHttpRequest=1-xml",
            cookies=cookies,
            headers=headers,
        )
        data = response.json()["js"]["data"]
        if data:
            return data
    except:
        pass
    raise Exception("Error getting EPG")