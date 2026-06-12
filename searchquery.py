from duckduckgo_search import DDGS

with DDGS() as ddgs:
    results = ddgs.text("current Prime Minister of India", max_results=3)

    for r in results:
        print(r)