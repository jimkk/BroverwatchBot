def get_rank(battletag):
    from urllib.request import urlopen
    import json
    url = "https://api.lootbox.eu/pc/us/" + battletag + "/profile"

    url = urlopen(url)
    data = url.read().decode("utf-8")
    json = json.loads(data)

    rank = json["data"]["competitive"]["rank"]
    
    return rank
