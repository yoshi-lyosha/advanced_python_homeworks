import json
from typing import Tuple, Optional

from aiohttp import web
import aioelasticsearch

from hw_3_aio_web_crawler.config import config as c


api_v1 = web.Application()
app = web.Application()


async def elasticsearch_client(_app):
    # connecting to the elasticsearch
    _app["es_client"] = aioelasticsearch.Elasticsearch(
        hosts=[
            {"host": c.CRAWLER_ELASTICSEARCH_HOST, "port": c.CRAWLER_ELASTICSEARCH_PORT}
        ]
    )
    yield
    await _app["es_client"].close()


api_v1.cleanup_ctx.append(elasticsearch_client)


api_v1_routes = web.RouteTableDef()


def validate_search_query(
    request: web.Request
) -> Tuple[Optional[dict], Optional[Tuple[dict, int, int]]]:
    """ Validates common mistakes """
    q = request.query.get("q")
    limit = request.query.get("limit")
    offset = request.query.get("offset")

    if not all([q, limit, offset]):
        error = {
            "value": request.query_string,
            "error": "you must pass non empty q, limit and offset",
        }
        return error, None

    try:
        q = json.loads(q)
    except json.JSONDecodeError:
        error = {"value": q, "error": "q must be valid elasticsearch query"}
        return error, None

    try:
        # casting to int and filtering negative values
        limit, offset = max(int(limit), 1), max(int(offset), 0)
    except ValueError:
        error = {
            "value": request.query_string,
            "error": "limit and offset must be positive int",
        }
        return error, None

    # finally
    return None, (q, limit, offset)


@api_v1_routes.get("/search")
async def api_v1_search_handler(request: web.Request):
    """
    Search api endpoint
    - /api/v1/search
      - q - query
      - limit - limit of search-hits to return
      - offset - offset (e.g. for pagination)
    """
    error, validated_params = validate_search_query(request)
    if error:
        return web.json_response({"status": 400, "body": error}, status=400)

    q, limit, offset = validated_params
    es: aioelasticsearch.Elasticsearch = request.app["es_client"]

    params = {}
    if limit:
        params["size"] = limit
    if offset:
        params["from"] = offset

    try:
        search_result = await es.search(
            index=c.CRAWLER_ELASTICSEARCH_INDEX,
            doc_type=c.CRAWLER_ELASTICSEARCH_DOC_TYPE,
            body={"query": q},
            params=params,
        )
    except aioelasticsearch.RequestError as e:
        return web.json_response(
            {"status": 400, "body": {"value": q, "error": f"bad query {e!r}"}},
            status=400,
        )

    return web.json_response(search_result, status=200)


app_routes = web.RouteTableDef()


@app_routes.get("/")
def index_handler(_: web.Request):
    """ Index page """
    index_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <title>Crawler API</title>
</head>
<body>
    <h3>Hello to the crawler app</h3>
    <h5>look at this great list of endpoints:</h5>
    <ul>
        <li>
            <a href="/search">Search page</a> that uses <a href="/api/v1/search">/api/v1/search</a>
        </li>
    </ul>
</body>
</html>
    """
    return web.Response(text=index_html, content_type="text/html")


@app_routes.get("/search")
async def api_v1_search_handler(_: web.Request):
    """ Search page with search-api use """
    search_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <title>Search</title>
</head>
<body>
    <h3>This is search page</h3>
    <h5>It's use api endpoint <a href="/api/v1/search">/api/v1/search</a>, that expects 3 query params</h5>
    <p> - q - query</p>
    <p> - limit - number of results</p>
    <p> - offset - offset (e.g. for pagination)</p>
    <p>This endpoint responds with search hits list, sorted by relevance</p>

    <form id="search_form">
        <table>
            <tr>
                <td>
                    <label for="q_input">q</label>
                    <input name="q" id="q_input" type="text" size="100">
                </td>
            </tr>
            <tr>
                <td>
                    <label for="limit_input">limit</label>
                    <input name="limit_input" id="limit_input" type="text">
                </td>
            </tr>
            <tr>
                <td>
                    <label for="offset_input">offset</label>
                    <input name="offset_input" id="offset_input" type="text">
                </td>
            </tr>
        </table>
        <input type="button" id="search_btn" value="Search this">
    </form>

    <br>

    <div id="search_result">
        <h3>Search result:</h3>
        <div id="search_result_container"></div>
    </div>

    <script>
        const search_api_uri = '/api/v1/search';
        const search_form_submit_btn = document.getElementById("search_btn");

        const search_result_container = document.getElementById("search_result_container");

        function formatParams( params ) {
            return "?" + Object
                .keys(params)
                .map(function(key){
                  return key+"="+encodeURIComponent(params[key])
                })
                .join("&")
}

        search_form_submit_btn.addEventListener('click', function () {
            let q = document.getElementById("q_input");
            let limit = document.getElementById("limit_input");
            let offset = document.getElementById("offset_input");

            let payload = {
                "q": q.value,
                "limit": limit.value,
                "offset": offset.value,
            };
            console.log(payload);

            let xhr = new XMLHttpRequest();
            xhr.open('GET', search_api_uri + formatParams(payload), true);
            xhr.send();
            xhr.onreadystatechange = function () {
                if (this.readyState !== 4) return;
                if (this.status !== 200) {
                    search_result_container.innerHTML = '';
                    search_result_container.innerText = 'status_code: ' + this.status + 
                    ' ' + this.statusText + '\\n' + this.response;
                    return
                }
                console.log(this.response);
                console.log(this.response['hits']);
                console.log(this.response.hits);

                let resp = JSON.parse(this.responseText);

                if (resp['hits']['total']['value'] === 0) {
                    search_result_container.innerHTML = '';
                    search_result_container.innerText = 'empty search result' + '\\n' + this.response;
                    return
                }
                search_result_container.innerHTML = '';
                search_result_container.hidden = true;

                let search_result_urls_list = document.createElement('ul');
                resp['hits']['hits'].forEach(function (element) {
                    let item = document.createElement('li');

                    let url = element['_source']['url'];
                    let url_a = document.createElement('a');
                    let url_a_text = document.createTextNode(url);
                    url_a.appendChild(url_a_text);
                    url_a.title = url;
                    url_a.href = url;
                    item.appendChild(url_a);

                    search_result_urls_list.appendChild(item);
                });

                search_result_container.appendChild(search_result_urls_list);
                search_result_container.removeAttribute('hidden');
            };
        });
    </script>
</body>
</html>
    """
    return web.Response(text=search_html, content_type="text/html")


api_v1.add_routes(api_v1_routes)

app.add_routes(app_routes)
app.add_subapp("/api/v1/", api_v1)


if __name__ == "__main__":
    web.run_app(app)
