### Asynchronous web sites crawler

This is a crawler that crawls some domain, and indexes each page text to elasticsearch  
Also it has some features as
- rps limiter
- html parsing in pool of processes
- n workers-coroutines for simultaneous crawl


Also there is a little API for searching indexed pages:
- /api/v1/search
  - q - query
  - limit - limit of search-hits to return
  - offset - offset (e.g. for pagination)


### How to start:
You need python 3.7 (bc i've used dataclasses) and docker (for elasticsearch)
```bash
# installing the requirements
pip3.7 install -r hw_3_aio_web_crawler/requirements.txt

# up the elasticsearch
docker-compose -f hw_3_aio_web_crawler/docker_compose.yml up

# up search app/api
python3.7 hw_3_aio_web_crawler/crawler_search_app.py

# run crawl script with hardcoded domain
python3.7 /Users/a.atanov/Code/Cources/advanced_python_homeworks/hw_3_aio_web_crawler/crawler.py
```