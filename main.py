from flask import Flask, render_template, redirect, url_for, request, jsonify, make_response
import urllib.parse
import json
from bs4 import BeautifulSoup
from solana import publickey
from solana import keypair
from solana.rpc.async_api import AsyncClient
from solana.system_program import TransferParams, transfer
from solana.transaction import Transaction
import asyncio
import aiohttp
import base58
from google.cloud import secretmanager
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
create = False

class Collections(db.Model):
    __tablename__ = "collections"
    _id = db.Column("id", db.Integer, nullable=False, primary_key=True)
    name = db.Column(db.String, nullable=False)
    thumbnail = db.Column(db.String, nullable=False)
    solanart = db.Column(db.String, nullable=True)
    alphaArt = db.Column(db.String, nullable=True)
    magicEden = db.Column(db.String, nullable=True)
    digitalEyes = db.Column(db.String, nullable=True)
    howrareis = db.Column(db.String, nullable=True)
    raritymon = db.Column(db.String, nullable=True)
    moonrank = db.Column(db.String, nullable=True)
    defaultrare = db.Column(db.String, nullable=True)
    raritys = db.relationship("Rarity", backref="collection")

class Rarity(db.Model):
    __tablename__ = "rarity"
    _id = db.Column("id", db.Integer, nullable=False, primary_key=True)
    name = db.Column(db.String, nullable=False)
    rank = db.Column(db.Integer, nullable=False)
    collection_id = db.Column(db.Integer, db.ForeignKey('collections.id'))

if create==True:
    db.create_all()

@app.route('/')
def home():
   return render_template("index.html")

@app.route('/addcollection', methods=["POST"])
def add():
    arguments = {"name": None, "solanart": None, "alphaArt": None, "magicEden": None, "digitalEyes": None, "thumbnail": None, "howrareis": None, "raritymon": None, "moonrank": None, "defaultrare": None, "SECRETKEY": None}
    arguments |= dict(request.args)
    secrets = secretmanager.SecretManagerServiceClient()
    SECRETKEY = secrets.access_secret_version(request={"name": "projects/654919614184/secrets/APIKEY/versions/1"}).payload.data.decode("utf-8")
    if arguments["SECRETKEY"] == SECRETKEY:
        try:
            addCollection(arguments["name"], arguments["thumbnail"], arguments["solanart"], arguments["alphaArt"], arguments["magicEden"], arguments["digitalEyes"], arguments["howrareis"], arguments["raritymon"], arguments["moonrank"], arguments["defaultrare"])
            return make_response(jsonify(message="Success"), 200)
        except:
            return make_response(jsonify(error="Response processing"), 422)
    else:
        return make_response(jsonify(error="Not allowed access"), 422)

@app.route('/addcollectionrarity', methods=["POST"])
def addrarity():
    arguments = {"name": None, "rank": None, "collection": None, "SECRETKEY": None}
    arguments |= dict(request.args)
    secrets = secretmanager.SecretManagerServiceClient()
    SECRETKEY = secrets.access_secret_version(request={"name": "projects/654919614184/secrets/APIKEY/versions/1"}).payload.data.decode("utf-8")
    if arguments["SECRETKEY"] == SECRETKEY:
        try:
            addRarity(arguments["name"], arguments["rank"], arguments["collection"])
            return make_response(jsonify(message="Success"), 200)
        except:
            return make_response(jsonify(error="Response processing"), 422)
    else:
        return make_response(jsonify(error="Not allowed access"), 422)

@app.route('/error')
def error():
   return render_template("error.html")

@app.route('/getcollections')
def getcollections():
    collections = asyncio.run(loadGetcollection())
    return make_response(jsonify(collections), 200)

@app.route('/getrarity')
def getrarity():
    rariry = asyncio.run(loadGetrarity())
    return make_response(jsonify(rariry), 200)

@app.route('/getresults', methods=["GET","POST"])
def getresults():
    if request.method == "POST":
        collection = request.values.get("collection")
        marketplaces = request.values.get("marketplace")
        raritysites = request.values.get("raritysite")
        signature = request.values.get("signature")
        donate = request.values.get("donate")
        marketops = json.loads(request.values.get("marketops"))
        rankingops = json.loads(request.values.get("rankingops"))
        error = False
        try:
            temp = asyncio.run(combine(collection, marketplaces, raritysites, marketops, rankingops))
        except Exception as e:
            error = True
            temp = False
        if not temp:
            error = True
        if error:
            if signature != "free":
                confirmed = asyncio.run(confirm(signature))
                if confirmed[0]:
                    asyncio.run(refund(confirmed[1], float(donate)))
            return redirect(url_for("error"))
        else:
            items = temp
        return render_template("results.html", items = items[0], floorprice = items[1])
    else:
        return redirect(url_for("home"))

@app.route("/robots.txt")
def robots_dot_txt():
    return "User-agent: *<br>Disallow: /"

async def getallCollections(session):
    collections = {}
    verified = Collections.query.all()
    for i in verified:
        collections[i.name.lower()] = {}
        if i.solanart:
            collections[i.name.lower()]["solanart"] = [i.solanart, i.thumbnail, True]
        if i.magicEden:
            collections[i.name.lower()]["magicEden"] = [i.magicEden, i.thumbnail, True]
        if i.alphaArt:
            collections[i.name.lower()]["alphaArt"] = [i.alphaArt, i.thumbnail, True]
        if i.digitalEyes:
            collections[i.name.lower()]["digitalEyes"] = [i.digitalEyes, i.thumbnail, True]
    urls = ["https://apis.alpha.art/api/v1/collections?order=volume&strip=1&n=2000", "https://api-mainnet.magiceden.io/all_collections", "https://qzlsklfacc.medianetwork.cloud/get_collections", "https://us-central1-digitaleyes-prod.cloudfunctions.net/collection-retriever"]
    tasks = []
    for url in urls:
        task = asyncio.ensure_future(fetch(url=url,session=session))
        tasks.append(task)
    marketPlaces = await asyncio.gather(*tasks,return_exceptions=True)
    acollection = {x["title"].lower():[x["slug"], x["thumbnail"], False] for x in json.loads(marketPlaces[0])["collections"]}
    mcollection = {x["name"].lower():[x["symbol"], x["image"], False] for x in json.loads(marketPlaces[1])["collections"]}
    scollection = {x["name"].lower():[x["url"], x["imgpreview"], False] for x in json.loads(marketPlaces[2])}
    dcollection = {x["name"].lower():[urllib.parse.quote_plus(x["name"]).lower(), "https://ik.imagekit.io/srjnqnjbpn9/"+x["thumbnail"], False] if x["thumbnail"][:4] != "http" else [urllib.parse.quote_plus(x["name"]), x["thumbnail"], False] for x in json.loads(marketPlaces[3])}
    if "danger valley" in scollection:
        scollection["danger valley ducks"] = scollection["danger valley"]
    for key in set().union(acollection, mcollection, scollection, dcollection):
        if key not in collections:
            collections[key] = {}
            if key in acollection:
                collections[key]["alphaArt"] = acollection[key]
            if key in mcollection:
                collections[key]["magicEden"] = mcollection[key]
            if key in scollection:
                collections[key]["solanart"] = scollection[key]
            if key in dcollection:
                collections[key]["digitalEyes"] = dcollection[key]
    return collections


async def alphaArt(collections, session):
    collection = collections[0]
    if collection:
        items = await post("https://apis.alpha.art/api/v1/collection", {"collectionId": collection, "orderBy": "PRICE_LOW_TO_HIGH", "status": ["BUY_NOW"], "traits": []}, session)
        listed = {x["title"]:[int(x["price"])/1000000000, ["https://alpha.art/t/"+x["mintId"],x["image"]]] for x in json.loads(items)["tokens"]}
        return listed
    return {}

async def magicEden(collections, session):
    collection = collections[0]
    if collection:
        info = await fetch("https://api-mainnet.magiceden.io/rpc/getCollectionEscrowStats/{}".format(collection), session)
        items = await fetch("https://api-mainnet.magiceden.io/rpc/getListedNFTsByQuery?q={}".format(urllib.parse.quote_plus('{"$match":{"collectionSymbol":"%s"},"$sort":{"takerAmount":1,"createdAt":-1},"$skip":0,"$limit":%s}' % (collection, json.loads(info)["results"]["listedCount"]))), session)
        listed = {x["title"]:[x["price"], ["https://magiceden.io/item-details/"+x["mintAddress"],x["img"]]] for x in json.loads(items)["results"]}
        return listed
    return {}

async def solanart(collections, session):
    collection = collections[0]
    if collection:
        listed = {}
        data = await fetch("https://qzlsklfacc.medianetwork.cloud/get_floor_price?collection={}".format(collection),session)
        count = json.loads(data)["count_listed"]
        for i in range(-(count // -100)):
            items = await fetch("https://qzlsklfacc.medianetwork.cloud/get_nft?collection={}&limit=100&fits=any&listed=true&page={}".format(collection, i), session)
            listed |= {x["name"]:[x["price"], ["https://solanart.io/search/?token="+x["token_add"], x["link_img"]]] for x in json.loads(items)["items"]}
        return listed
    return {}

async def digitalEyes(collections, session):
    collection = collections[0]
    if collection:
        items = await fetch("https://us-central1-digitaleyes-prod.cloudfunctions.net/offers-retriever?collection={}&price=asc".format(collection), session)
        listed = {x["metadata"]["name"]:[x["price"]/1000000000, [f"https://digitaleyes.market/item/{collection}/"+x["mint"]+"?pk="+x["pk"], x["metadata"]["image"]]] for x in json.loads(items)["offers"]}
        return listed
    return {}

# {"name":["price",["url", "image"], "rank", "value"]}
 
async def howrareis(collection, session):
    results = json.loads(await fetch("https://howrare.is/api/v0.1/collections" + collection, session=session))
    if results["result"]["api_response"] == "Success":
        items = {x["name"]: int(x["rank"]) for x in results["result"]["data"]["items"]}
        return items
    else:
        return

async def moonrank(collection, session):
    itemsPage = await fetch(f"https://moonrank.app/mints/{collection}", session)
    stuff = json.loads(itemsPage)["mints"]
    ranked = {x["name"]:x["rank"] for x in stuff}
    return ranked


async def raritymon(collection, session):
    itemsl = {}
    tasks = []
    page = await fetch(f"https://www.raritymon.com/Collections?collection={collection}&page=0",session)
    soup = BeautifulSoup(page, "html.parser")
    itemNo = int(soup.find("p", class_="color_black").text.strip())
    for i in range(-(itemNo // -24)):
        url = f"https://www.raritymon.com/Collections?collection={collection}&page={i}"
        task = asyncio.ensure_future(fetch(url=url,session=session))
        tasks.append(task)
    responses = await asyncio.gather(*tasks,return_exceptions=True)
    for i in responses:
        collectionSoup = BeautifulSoup(i, "html.parser")
        items = collectionSoup.find_all("div", class_="card__item four")
        itemsl |= {i.find("p", class_="txt_xs").text.strip(): int(i.find("span", class_="color_brand d-block txt_xs").text.strip()[5:]) for i in items}
    return itemsl


def rank(listed):
    for i in listed:
        q = 3/4
        x = listed[i][2]
        y = listed[i][0]
        for j in listed:
            q += (u(x - listed[j][2]) * u(y - listed[j][0]))
        listed[i].append(q)
    return listed

def u(t):
    if t > 0:
        return 1
    if t == 0:
        return 1/2
    if t < 0:
        return 0 


async def combine(collection, marketplaces, raritysites, marketops, rankingops):
    my_conn = aiohttp.TCPConnector(limit=10)
    async with aiohttp.ClientSession(connector=my_conn) as session:
        solanartc = {}
        alphaArtc = {}
        magicEdenc = {}
        digitalEyesc = {}
        if marketplaces == "all":
            if "solanart" in marketops:
                solanartc = await solanart(marketops["solanart"], session)
            if "alphaArt" in marketops:
                alphaArtc = await alphaArt(marketops["alphaArt"], session)
            if "magicEden" in marketops:
                magicEdenc = await magicEden(marketops["magicEden"], session)
            if "digitalEyes" in marketops:
                digitalEyesc = await digitalEyes(marketops["digitalEyes"], session)
        elif marketplaces == "solanart":
            solanartc = await solanart(marketops["solanart"], session)
        elif marketplaces == "alphaArt":
            alphaArtc = await alphaArt(marketops["alphaArt"], session)
        elif marketplaces == "magicEden":
            magicEdenc = await magicEden(marketops["magicEden"], session)
        elif marketplaces == "digitalEyes":
            digitalEyesc = await digitalEyes(marketops["digitalEyes"], session)
        verfied = Collections.query.filter_by(name=collection).first()
        if verfied:
            if verfied.defaultrare == raritysites:
                ranks = {x.name : x.rank for x in verfied.raritys}
            else:
                verfied = None
        if not verfied:
            if raritysites == "auto":
                if "moonrank" in rankingops:
                    ranks = await moonrank(rankingops["moonrank"], session)
                elif "howrareis" in rankingops:
                    ranks = await howrareis(rankingops["howrareis"], session)
                elif "raritymon" in rankingops:
                    ranks = await raritymon(rankingops["raritymon"], session)
            elif raritysites == "moonrank":
                ranks = await moonrank(rankingops["moonrank"], session)
            elif raritysites == "howrareis":
                ranks = await howrareis(rankingops["howrareis"], session)
            elif raritysites == "raritymon":
                ranks = await raritymon(rankingops["raritymon"], session)
    listed = solanartc | alphaArtc | magicEdenc | digitalEyesc
    for x in listed.copy():
        if x in ranks:
            listed[x].append(int(ranks[x]))
            if listed[x][0] == 0:
                listed.pop(x)
        else:
            listed.pop(x)
    if not listed:
        return False
    listed = rank(listed)
    listed = list(listed.items())
    floor = min(listed, key=lambda x: x[1][0])[1][0]
    listed.sort(key=lambda tup: tup[1][3])
    best = []
    for i in listed:
        if i[1][3] == 1:
            best.append(i)
    maxPrice = max(best, key=lambda x: x[1][0])[1][0]
    maxRank = max(best, key=lambda x: x[1][2])[1][2]
    sortedList = sorted(best, key=lambda x : ((x[1][0]/maxPrice) + (x[1][2]/maxRank))/2)
    return sortedList, floor

async def confirm(signature):
    async with AsyncClient("https://api.mainnet-beta.solana.com") as client:
        try:
            res1 = await client.confirm_transaction(signature)
            if res1["result"]["value"][0]["confirmationStatus"] == "finalized":
                res = await client.get_confirmed_transaction(signature)
                if res["result"]["transaction"]["message"]["accountKeys"][1] == "FqdxQD3t1CtECDPUDeB19mV26JzcTTfS8Hz8CBCpqLTS":
                    return (True, res["result"]["transaction"]["message"]["accountKeys"][0])
                return (False,)
            else:
                return (False,)
        except:
            return (False,)

async def fetch(url, session , headers=None):
    async with session.get(url, headers=headers) as response:
        res = await response.read()
    return res

async def post(url, data, session):
    async with session.post(url, json=data) as response:
        res = await response.read()
    return res

async def loadGetcollection():
    my_conn = aiohttp.TCPConnector(limit=10)
    async with aiohttp.ClientSession(connector=my_conn) as session:
        return await getallCollections(session)

async def refund(address, amount):
    secrets = secretmanager.SecretManagerServiceClient()
    SECRETKEY = secrets.access_secret_version(request={"name": "projects/654919614184/secrets/SECRETKEY/versions/1"}).payload.data.decode("utf-8")
    byte_array = base58.b58decode(SECRETKEY)
    keys = keypair.Keypair.from_secret_key(byte_array)
    txn = Transaction().add(transfer(TransferParams(from_pubkey=keys.public_key, to_pubkey=publickey.PublicKey(address), lamports=int(1000000000 * amount))))
    async with AsyncClient("https://api.mainnet-beta.solana.com") as client:
        await client.send_transaction(txn, keys)

async def getAllRarity(session):
    collections = {}
    verified = Collections.query.all()
    for i in verified:
        collections[i.name.lower()] = {"defaultrare": i.defaultrare}
        if i.moonrank:
            collections[i.name.lower()]["moonrank"] = i.moonrank
        if i.howrareis:
            collections[i.name.lower()]["howrareis"] = i.howrareis
        if i.raritymon:
            collections[i.name.lower()]["raritymon"] = i.raritymon
    hdata = await fetch("https://howrare.is/api/v0.1/collections", session)
    mpage = await fetch("https://moonrank.app/", session)
    msoup = BeautifulSoup(mpage, "html.parser")
    mcollections = {x["data-mr-name"].lower() : x["data-mr-id"] for x in msoup.select("div[data-mr-id]")}
    rpage = await fetch("https://raritymon.com/", session)
    rsoup = BeautifulSoup(rpage, "html.parser")
    ritems = rsoup.find_all("script")[-2].text.strip().split("[")[1].split("]")[0].strip().split("//")[0].split(",")
    rcollection = {}
    for i in range(len(ritems)):
        if i % 2 == 0:
            key = ritems[i].strip()[9:-1]
        else:
            value = ritems[i].strip()[8:-2]
            rcollection[key.lower()] = value
    hcollections = {x["name"].lower():x["url"] for x in json.loads(hdata)["result"]["data"]}
    hcollections = {}
    if "solanamonkeybusiness (smb)" in hcollections:
        hcollections["solana monkey business"] = hcollections["solanamonkeybusiness (smb)"]
    for key in set().union(mcollections, rcollection, hcollections):
        if key not in collections:
            collections[key] = {}
            if key in mcollections:
                collections[key]["moonrank"] = mcollections[key]
            if key in rcollection:
                collections[key]["raritymon"] = rcollection[key]
            if key in hcollections:
                collections[key]["howrareis"] = hcollections[key]
    return collections

def addCollection (name, thumbnail, solanart, alphaArt, magicEden, digitalEyes, howrareis, raritymon, moonrank, defaultrare):
    col = Collections(name=name, thumbnail=thumbnail, solanart=solanart, alphaArt=alphaArt, magicEden=magicEden, digitalEyes=digitalEyes, howrareis=howrareis, raritymon=raritymon, moonrank=moonrank, defaultrare=defaultrare)
    db.session.add(col)
    db.session.commit()

def addRarity (name, rank, collectionName):
    rarity = Rarity(name=name, rank=rank)
    collection = Collections.query.filter_by(name=collectionName).first()
    collection.raritys.append(rarity)
    db.session.add(rarity)
    db.session.commit()

async def loadGetrarity():
    my_conn = aiohttp.TCPConnector(limit=10)
    async with aiohttp.ClientSession(connector=my_conn) as session:
        return await getAllRarity(session)

if __name__ == '__main__':
   app.run()
