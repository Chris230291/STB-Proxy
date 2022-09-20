from logging import error
import requests
from retrying import retry
from urllib.parse import urlparse
import re
import math
import json

@retry(stop_max_attempt_number=4, wait_exponential_multiplier=200, wait_exponential_max=2000)
def getUrl(url, proxy=None):
    def parseResponse(url, data):
        java = data.text.replace(' ', '').replace("'", '').replace('+', '')
        pattern = re.search(r'varpattern.*\/(\(http.*)\/;', java).group(1)
        result = re.search(pattern, url)
        protocolIndex = re.search(
            r'this\.portal_protocol.*(\d).*;', java).group(1)
        ipIndex = re.search(r'this\.portal_ip.*(\d).*;', java).group(1)
        pathIndex = re.search(r'this\.portal_path.*(\d).*;', java).group(1)
        protocol = result.group(int(protocolIndex))
        ip = result.group(int(ipIndex))
        path = result.group(int(pathIndex))
        portalPatern = re.search(
            r'this\.ajax_loader=(.*\.php);', java).group(1)
        portal = portalPatern.replace('this.portal_protocol', protocol).replace(
            'this.portal_ip', ip).replace('this.portal_path', path)
        return portal

    url = urlparse(url).scheme + "://" + urlparse(url).netloc
    urls = ["/c/xpcom.common.js", "/client/xpcom.common.js", "/c_/xpcom.common.js",
            "/stalker_portal/c/xpcom.common.js", "/stalker_portal/c_/xpcom.common.js"]

    proxies = {"http": proxy, "https": proxy}
    headers = {"User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C)"}

    try:
        for i in urls:
            try:
                response = requests.get(
                    url + i, headers=headers, proxies=proxies)
            except:
                response = None
            if response:
                return parseResponse(url + i, response)
    except:
        pass
    raise Exception("Error getting portal URL")


@retry(stop_max_attempt_number=4, wait_exponential_multiplier=200, wait_exponential_max=2000)
def getToken(url, mac, proxy=None):
    proxies = {"http": proxy, "https": proxy}
    cookies = {"mac": mac, "stb_lang": "en", "timezone": "Europe/London"}
    headers = {"User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C)"}
    try:
        response = requests.get(
            url + "?type=stb&action=handshake&JsHttpRequest=1-xml",
            cookies=cookies,
            headers=headers,
            proxies=proxies
        )
        data = response.json()
        token = data["js"]["token"]
        if token:
            getProfile(url, mac, token, proxy)
            return token
    except:
        pass
    raise Exception("Error getting token")


@retry(stop_max_attempt_number=4, wait_exponential_multiplier=200, wait_exponential_max=2000)
def getProfile(url, mac, token, proxy=None):
    proxies = {"http": proxy, "https": proxy}
    cookies = {"mac": mac, "stb_lang": "en", "timezone": "Europe/London"}
    headers = {
        "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C)",
        "Authorization": "Bearer " + token,
    }
    try:
        response = requests.get(
            url + "?type=stb&action=get_profile&JsHttpRequest=1-xml",
            cookies=cookies,
            headers=headers,
            proxies=proxies
        )
        data = response.json()
        if data:
            return data
    except:
        pass
    raise Exception("Error getting profile")


def getExpires(url, mac, token, proxy=None):
    proxies = {"http": proxy, "https": proxy}
    cookies = {"mac": mac, "stb_lang": "en", "timezone": "Europe/London"}
    headers = {
        "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C)",
        "Authorization": "Bearer " + token,
    }
    try:
        response = requests.get(
            url + "?type=account_info&action=get_main_info&JsHttpRequest=1-xml",
            cookies=cookies,
            headers=headers,
            proxies=proxies
        )
        data = response.json()
        expire = data["js"]["phone"]
        if expire:
            return expire
    except:
        pass
    return "Unkown"


@retry(stop_max_attempt_number=4, wait_exponential_multiplier=200, wait_exponential_max=2000)
def getAllChannels(url, mac, token, proxy=None, genres=None):
    proxies = {"http": proxy, "https": proxy}
    cookies = {"mac": mac, "stb_lang": "en", "timezone": "Europe/London"}
    headers = {
        "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C)",
        "Authorization": "Bearer " + token,
    }
    try:
        response = requests.get(
            url
            + "?type=itv&action=get_all_channels&force_ch_link_check=&JsHttpRequest=1-xml",
            cookies=cookies,
            headers=headers,
            proxies=proxies
        )
        channels = response.json()["js"]["data"]
        if genres:
            adults_genres = [k for k, v in genres.items() if 'Adult' in v or 'XXX'in v]
            try: 
                for value in adults_genres:
                    for numbers in range(50):
                        response = requests.get(
                        url
                        + f'?type=itv&action=get_ordered_list&genre={value}&p={numbers}&JsHttpRequest=1-xml',
                        cookies=cookies,
                        headers=headers,
                        proxies=proxies
                        )
                        if response.json()["js"]["data"]:
                            adults = response.json()["js"]["data"]
                            channels += adults
            except Exception as err: 
                print(f"New Error Ocurred: {err}")
                pass

        if channels:
            return channels
    except:
        pass
    raise Exception("Error getting channels")


@retry(stop_max_attempt_number=4, wait_exponential_multiplier=200, wait_exponential_max=2000)
def getGenres(url, mac, token, proxy=None):
    proxies = {"http": proxy, "https": proxy}
    cookies = {"mac": mac, "stb_lang": "en", "timezone": "Europe/London"}
    headers = {
        "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C)",
        "Authorization": "Bearer " + token,
    }
    try:
        response = requests.get(
            url + "?action=get_genres&type=itv&JsHttpRequest=1-xml",
            cookies=cookies,
            headers=headers,
            proxies=proxies
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


@retry(stop_max_attempt_number=4, wait_exponential_multiplier=200, wait_exponential_max=2000)
def getLink(url, mac, token, cmd, proxy=None):
    proxies = {"http": proxy, "https": proxy}
    cookies = {"mac": mac, "stb_lang": "en", "timezone": "Europe/London"}
    headers = {
        "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C)",
        "Authorization": "Bearer " + token,
    }
    try:
        response = requests.get(
            url + "?type=itv&action=create_link&cmd=" + cmd +
            "&series=0&forced_storage=false&disable_ad=false&download=false&force_ch_link_check=false&JsHttpRequest=1-xml",
            cookies=cookies,
            headers=headers,
            proxies=proxies
        )
        data = response.json()
        link = data["js"]["cmd"].split()[-1]
        if link:
            return link
    except:
        pass
    raise Exception("Error getting link")


@retry(stop_max_attempt_number=4, wait_exponential_multiplier=200, wait_exponential_max=2000)
def getEpg(url, mac, token, period, proxy=None):
    proxies = {"http": proxy, "https": proxy}
    cookies = {"mac": mac, "stb_lang": "en", "timezone": "Europe/London"}
    headers = {
        "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C)",
        "Authorization": "Bearer " + token,
    }
    try:
        response = requests.get(
            url + "?type=itv&action=get_epg_info&period=" +
            str(period) + "&JsHttpRequest=1-xml",
            cookies=cookies,
            headers=headers,
            proxies=proxies
        )
        data = response.json()["js"]["data"]
        if data:
            return data
    except:
        pass
    raise Exception("Found no EPG data")


def getVods(url, mac, token, proxy=None):
    proxies = {"http": proxy, "https": proxy}
    cookies = {"mac": mac, "stb_lang": "en", "timezone": "Europe/London"}
    headers = {
        "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C)",
        "Authorization": "Bearer " + token,
    }
    try:
        response = requests.get(
            url + "?type=vod&action=get_ordered_list&p=1&JsHttpRequest=1-xml",
            cookies=cookies,
            headers=headers,
            proxies=proxies
        )
        data = response.json()["js"]
        pages = math.ceil(int(data["total_items"]) /
                          int(data["max_page_items"]))
        vods = response.json()["js"]["data"]

        for i in range(2, pages):
            response = requests.get(
                url + "?type=vod&action=get_ordered_list&p=" +
                str(i) + "&JsHttpRequest=1-xml",
                cookies=cookies,
                headers=headers,
                proxies=proxies
            )
            vods = vods + response.json()["js"]["data"]
        if vods:
            return vods
    except:
        pass
    raise Exception("Found no VOD data")


@retry(stop_max_attempt_number=4, wait_exponential_multiplier=200, wait_exponential_max=2000)
def getVodLink(url, mac, token, cmd, proxy=None):
    proxies = {"http": proxy, "https": proxy}
    cookies = {"mac": mac, "stb_lang": "en", "timezone": "Europe/London"}
    headers = {
        "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C)",
        "Authorization": "Bearer " + token,
    }
    try:
        response = requests.get(
            url + "?type=vod&action=create_link&cmd=" + cmd + "&JsHttpRequest=1-xml",
            cookies=cookies,
            headers=headers,
            proxies=proxies
        )
        data = response.json()
        link = data["js"]["cmd"].split()[-1]
        if link:
            return link
    except:
        pass
    raise Exception("Error getting link")


def getSeries(url, mac, token, proxy=None):
    proxies = {"http": proxy, "https": proxy}
    cookies = {"mac": mac, "stb_lang": "en", "timezone": "Europe/London"}
    headers = {
        "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C)",
        "Authorization": "Bearer " + token,
    }
    try:
        response = requests.get(
            url + "?type=series&action=get_ordered_list&p=1&JsHttpRequest=1-xml",
            cookies=cookies,
            headers=headers,
            proxies=proxies
        )
        data = response.json()["js"]
        if data:
            return data
    except:
        pass
    raise Exception("Found no VOD data")


def test(url, mac, token, proxy=None):
    proxies = {"http": proxy, "https": proxy}
    cookies = {"mac": mac, "stb_lang": "en", "timezone": "Europe/London"}
    headers = {
        "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C)",
        "Authorization": "Bearer " + token,
    }
    try:
        response = requests.get(
            url + "?type=series&action=get_ordered_list&movie_id=2198%3A1&category=2198:1&genre=*&season_id=0&episode_id=0&force_ch_link_check=&from_ch_id=0&fav=0&sortby=added&hd=0&not_ended=0&p=1&JsHttpRequest=1-xml",
            cookies=cookies,
            headers=headers,
            proxies=proxies
        )
        data = response.json()["js"]
        if data:
            return data
    except:
        pass
    raise Exception("Found no VOD data")
