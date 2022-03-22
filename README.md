# STB-Proxy

- Play STB portal streams in regular m3u media players
- Responds as HD Homerun for Plex etc
- Configuration through web UI
- Combine multiple portals
- Enable/disable channels individually
- Rename channels
- Set custom genres
- Modify channel numbers
- Override epg
- Set fallback channels
- Support for multiple MACs/Streams per Portal

# Docker
- Map whichever port you like to the default `8001`
- `HOST` should be the docker hosts ip + the port you chose
- Mounting `/config` is required for settings to persist through restarts
- To configure go to the HOST + port in a browser eg 10.0.1.200:8084

example:
```
docker create \
--name=STB-Proxy \
--restart=always \
-p 8084:8001 \
-e HOST=10.0.1.200:8084 \
-v </host/path>:/config \
chris230291/stb-proxy:stable
```

# Without Docker

- Requires: `python 3` `flask` `requests` `retrying` `ffmpeg`
- Download the repo
- Doubble click `app.py`
- Go to `http://localhost:8001` in a browser and enter Portal URL + MAC

# Note

I am not a programmer. Most of the stuff involved with getting this working (excluding some basic python knowledge) I learnt while putting this app together. If you see any room for improvement please make suggestions and/or pull requests.
