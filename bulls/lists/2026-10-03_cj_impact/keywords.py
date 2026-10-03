"""Brand keyword chosen for each offer: the search that best represents buying the brand (not the company's legal name).
Ambiguous words get a qualifier (ring -> ring doorbell) so unrelated searches are not counted."""
KEYWORD = {
"12GO":"12go","Abelssoft Int":"abelssoft","Abracadabra NYC":"abracadabra nyc","Acronis International GmbH":"acronis",
"Adblockultimate.net":"adblock ultimate","Aiper":"aiper","AliExpress - Global":"aliexpress","AOMEI":"aomei",
"Ashampoo INT":"ashampoo","Bulldog Online Yoga & Fitness":"bulldog online yoga","Contabo COM":"contabo","Coofandy":"coofandy",
"DirectDeals":"directdeals","Dynadot.com":"dynadot","EaseUS":"easeus","Elementor":"elementor",
"eReleases Press Release Distribution":"ereleases","Gandi":"gandi","GearUP":"gearup booster","HideMy.Name global":"hidemy.name",
"Hostpapa":"hostpapa","Incogni":"incogni","Intego Antivirus Security":"intego","Kaspersky Australia & New Zealand":"kaspersky",
"Kaspersky CEE":"kaspersky","Kaspersky LATAM":"kaspersky","Kaspersky UK":"kaspersky","MiniTool":"minitool","Movavi":"movavi",
"Mysterium VPN":"mysterium vpn","Netart APAC":"netart","NordPass":"nordpass","NordVPN":"nordvpn","O&O Software":"o&o software",
"Panda Office Limited":"panda office","Paragon Software Group":"paragon software","Parallels":"parallels desktop",
"Proton Partners Program":"proton vpn","Quark Software":"quarkxpress","RealDefense":"iolo system mechanic","Rexing":"rexing",
"RoboForm Password Manager Affiliate Program":"roboform","Surfshark":"surfshark","Tanga.com":"tanga","Tello":"tello mobile",
"UPDF":"updf","Veepn.com":"veepn","Velocity Outdoor – Ravin/CenterPoint/Valhalla":"ravin crossbows","Verizon":"verizon",
"Vrbo":"vrbo","WiTopia | SecureMyEmail | personalVPN":"witopia","Wondershare":"wondershare",
"Airalo":"airalo","Airwallex - Affiliate Program":"airwallex","Amotopart Fairing Creator Recruitment":"amotopart",
"Angles90":"angles90","AppSumo":"appsumo","Arbiship - eBay Dropshipping Automation":"arbiship","Aspiron":"aspiron",
"Baby Deep Sleep":"baby deep sleep","Baby Sunnies":"baby sunnies","Base44":"base44","BdThemes Affiliate Program":"bdthemes",
"Big Bat Box":"big bat box","Bitdefender":"bitdefender","Blockchain Council":"blockchain council","Bluehost":"bluehost",
"Bodyotics affiliate program":"bodyotics","Byre Affiliate program":"byre","BytePlus":"byteplus","CapCut Affiliate Program":"capcut",
"Carwow UK":"carwow","Charlemange":"charlemagne premium","Cloudfield":"cloudfield","Cloudways":"cloudways",
"Coach Soak affiliate program":"coach soak","Cricut US & CAN":"cricut","DHgate":"dhgate","DocHub":"dochub",
"DumbleScore":"dumblescore","Envato Market":"envato market","Eufy NL":"eufy","Eureka US":"eureka vacuum","eyeson":"eyeson",
"Fabletics Performance":"fabletics","FILA SEA":"fila","Fofana affiliate program":"fofana","Freecash":"freecash","GAFLY":"gafly",
"GeekBuying":"geekbuying","Gemini Exchange":"gemini exchange","Hana Emi Affiliate program":"hana emi",
"Happy Sinks Affiliate Program":"happy sinks","Hieno Affiliate program":"hieno supplies","Hostinger":"hostinger",
"Humble Bundle, Inc.":"humble bundle","iMobie":"imobie","INDO Trick Scooter affiliate program":"indo trick scooter",
"InMotion Hosting":"inmotion hosting","Jackery NL":"jackery","jAlbum Affiliate Program":"jalbum","Lenovo Argentina":"lenovo",
"Lenovo Chile":"lenovo","Lenovo Colombia":"lenovo","Lenovo India":"lenovo","LifeLock":"lifelock","Lightailing":"lightailing",
"LINNER OTC Heraing Aids":"linner hearing aids","Lumibricks":"lumibricks","Lux":"lux sports","MACROSOFT STORE S.R.L.":"macrosoft",
"Mail Backup X":"mail backup x","Martinic Audio":"martinic","Maya Mobile - Affiliate Program":"maya mobile","Meta Box":"meta box wordpress",
"MindManager":"mindmanager","Mioeco":"mioeco","Modlily":"modlily","MushroomSupplies.com":"mushroomsupplies","Norton":"norton",
"Nudco":"nudco","Omfort":"omfort","Onemile":"onemile bike","OnePlus FR":"oneplus","Ontaki Affiliate program":"ontaki",
"OPPO TH":"oppo","Parallels.cn":"parallels desktop","Parallels.com":"parallels desktop","ParisRhone":"parisrhone",
"Pelago by Singapore Airlines":"pelago","Penchant for Pleasure":"penchant for pleasure","POP MART Americas Inc.":"pop mart",
"PosterMyWall":"postermywall","Preply Learners":"preply","Pure Scentum Affiliate Program":"pure scentum",
"Puzzle Ready affiliate program":"puzzle ready","RAVPower":"ravpower","Relhost - Amazon Seller - US":"artemis ads",
"Rowabi LLC":"rowabi","Shopify":"shopify","Silginnes":"silginnes","Silver Cuisine":"silver cuisine",
"Smile Makers Collection":"smile makers","Striking Viking":"striking viking","Throwback Traits":"throwback traits",
"TicketNetwork Affiliate Program":"ticketnetwork","Tiny Land":"tiny land","TORRAS":"torras","Udemy":"udemy","Ultahost":"ultahost",
"UPERFECT":"uperfect","Upwork":"upwork","Virgin Voyages":"virgin voyages","Vivid Seats":"vivid seats","WPS SOFTWARE PTE.LTD.":"wps office",
"A-Premium Auto Parts":"a-premium","AosomCA":"aosom","AosomUK":"aosom","apexwill ebike":"apexwill","Avast Software":"avast",
"AVG":"avg antivirus","Avira":"avira","BrandsMart USA":"brandsmart","CASETiFY UK":"casetify","ClassDojo - Creator":"classdojo tutor",
"Corel":"coreldraw","Coursera B2C Affiliate Program":"coursera","de.ulike.com":"ulike","djiusa.com":"dji","ELEGOO":"elegoo",
"Envato":"envato elements","HubSpot":"hubspot","IceVPN":"icevpn","Identity Guard":"identity guard","iMyFone Software (old）":"imyfone",
"Innovation Refunds":"innovation refunds","isinwheel.fr":"isinwheel","Kamatera":"kamatera","lightsaber.com":"lightsaber.com",
"Margovil":"margovil","METRO X":"metro x app","Modello Turbo LLC":"modello turbo","NordLayer":"nordlayer","Novyro":"novyro",
"Odinlake":"odinlake","PopAi AI Sheets":"popai","Promeed":"promeed","PureVPN":"purevpn","PYPROXY":"pyproxy",
"Renderforest":"renderforest","Ria Money Transfer":"ria money transfer","Ring":"ring doorbell","RingConn":"ringconn",
"ScalaHosting":"scalahosting","shop.homestyler.com":"homestyler","SilkSilky Affiliate Program":"silksilky","Spaceship":"spaceship domains",
"TheHues":"thehues","Thordata Global Residential Proxy":"thordata","Trend Micro APAC Affiliate Program":"trend micro",
"TunePat":"tunepat","us.ulike.com":"ulike","Vista Social":"vista social","Wegic":"wegic","YouFibre":"youfibre",
}
# Where the offer's GEO doesn't say, the country the website points to (CJ rows have no GEO in the export).
DOMAIN_GEO = {"kaspersky.com.au": "AU", "kaspersky.cz": "CZ", "latam.kaspersky.com": "MX", "kaspersky.co.uk": "GB",
              "parallels.cn": "CN"}

LOCATION = {"US": 2840, "GB": 2826, "CA": 2124, "NL": 2528, "FR": 2250, "DE": 2276, "IN": 2356, "AR": 2032, "CL": 2152,
            "CO": 2170, "TH": 2764, "AU": 2036, "CZ": 2203, "MX": 2484, "SG": 2702}


def measure_geo(geo, website):
    """Country whose Google volume we measure. Single-country offers: that country. US in the list, WORLDWIDE or no
    GEO given: US (our main market; stated as an assumption). Otherwise GB, then DE, then the first country.
    Returns None where Google search volume is not meaningful (China)."""
    if website in DOMAIN_GEO:
        g = DOMAIN_GEO[website]
        return None if g == "CN" else g
    geos = [g.strip() for g in (geo or "").split(",") if g.strip()]
    if not geos or "WORLDWIDE" in geos or "US" in geos:
        return "US"
    if geos == ["CN"]:
        return None
    for g in ("GB", "DE"):
        if g in geos:
            return g
    return next((g for g in geos if g in LOCATION and g != "CN"), "US")
