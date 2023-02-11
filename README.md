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


# Setup

Install the latest Docker image with...

```
docker create \
--name=STB-Proxy \
--restart=always \
-p 8084:8001 \
-e HOST=10.0.1.200:8084 \
-v </host/path>:/config \
chris230291/stb-proxy:latest
```

Map whichever port you like to the default `8001`
`HOST` should be the docker hosts ip + the port you chose
Mounting `/config` is required for settings to persist through restarts
To configure go to the `HOST` in a browser eg 10.0.1.200:8084