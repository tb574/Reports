import csv, math, html
# kind F = payout per sale known in USD (fixed / observed / research estimate); P = % offer, order value unknown
# (rank, brand, geo, source, sv, cpc, kind, earn_usd_or_rate, basis, why, risk)
R=[
("NCL – Norwegian Cruise Line","US","Intango",368000,0.26,"F",150,"fixed $150 (lowest listed)","Cruise bookings pay a flat $150 while the brand click costs only $0.26. Highest payout-to-click ratio of all offers with a known payout.","Intango is a sub-network: confirm $150 is what reaches you and what counts as a booking."),
("waipu.tv","DE","digidip",450000,0.09,"F",39.29,"fixed up to €35 (top listed tier)","Very cheap clicks ($0.09) against a fixed subscription payout. Streaming sign-ups convert well from brand searches.","€35 is the top tier; the common plan may pay less. German ads needed."),
("sky.de","DE","digidip",450000,0.06,"F",22.45,"€20 average actually paid per sale (digidip observed)","Cheapest clicks in the list ($0.06) and a payout based on real past sales, not an estimate.","Many sky searches are existing customers (login, support); exclude those with negative keywords."),
("Ulys (toll badge)","FR","digidip",301000,0.03,"F",10.10,"fixed €9","Clicks cost $0.03, so even a small fixed payout reaches 5x ROAS at 1.5% conversion.","Small payout per sale: needs volume; French ads needed."),
("1&1","DE","digidip",450000,0.29,"F",89.80,"fixed up to €80 (top listed tier)","Internet/mobile contracts pay a high fixed amount; brand searches show buying intent for tariffs.","€80 is the top tier (likely a DSL/fibre contract); mobile may pay less."),
("Virgin Voyages","US","Impact (NYJL)",368000,0.90,"F",240,"12% × ~$2,000 cabin (public estimate)","Expensive product × 12% commission = large payout per booking; you are approved directly on Impact.","Order value is a public estimate; the test must confirm it."),
("Lenovo India","IN","Impact (NYJL)",450000,0.09,"F",14.34,"4% × ~₹34,000 laptop (public estimate), paid in INR","Extremely cheap clicks ($0.09) for laptop buyers; 4% of a laptop covers them many times over.","Payout in rupees; order value is an estimate; Indian market CR unknown."),
("Linvosges","FR","pickalink",201000,0.16,"F",25.21,"fixed €22.46 (lowest listed)","Premium French home-linen brand with a fixed payout and cheap clicks.","pickalink is a sub-network: confirm net payout."),
("Freebox","FR","digidip",823000,0.45,"F",57.02,"€50.80 average actually paid per sale (digidip observed)","Internet box subscriptions pay a high observed commission; 823k searches.","Many searches are existing subscribers (Freebox OS, support)."),
("Süddeutsche Zeitung","DE","digidip",450000,1.40,"F",145.93,"fixed up to €130 (top listed tier)","Very high fixed payout for a subscription.","Most searches are readers, not buyers: lower intent. €130 is the top tier."),
("DirecTV","US","Intango",1220000,1.22,"F",120,"fixed $120 (lowest listed)","High fixed payout per new TV subscription; 1.2M searches.","Many searches are existing customers (bill pay, login)."),
# ---- queue
("ZipRecruiter","US","Intango",823000,1.11,"F",105,"fixed $105 (lowest listed)","High fixed payout.","Payout is most likely for employers; most searchers are job seekers."),
("Kampgrounds of America (KOA)","US","Shopnomix",201000,0.16,"F",15,"fixed 15 (currency not stated)","Cheap clicks, campsite bookings.","Currency of the payout not stated."),
("Free Mobile","FR","digidip",2240000,0.26,"F",24.08,"€21.45 average actually paid (digidip observed)","2.2M searches, real observed payout.","Existing customers dominate searches."),
("Coolblue","DE","digidip",201000,0.08,"P",9,"9% (digidip observed rate)","Electronics retailer: big baskets × 9% against $0.08 clicks.","Order value not verified."),
("Eventim","DE","digidip",1830000,0.07,"P",25,"25% (digidip observed rate)","1.8M searches, $0.07 clicks, high observed rate on tickets.","25% is unusually high; confirm it is % of the ticket price."),
("OBI","DE","Intango",1500000,0.04,"P",10,"10% (listed)","DIY store, 1.5M searches, $0.04 clicks.","Order value not verified; Intango rate basis to confirm."),
("Temu","FR","pickalink",3350000,0.08,"P",23.27,"23.3% (listed)","Huge volume, cheap clicks, very high rate.","Temu usually pays new users only; order value not verified."),
("Temu","DE","pickalink",3350000,0.10,"P",23.27,"23.3% (listed)","Same as Temu FR.","Same as Temu FR."),
("Build-A-Bear","US","Intango",823000,0.04,"P",10,"10% (listed)","$0.04 clicks, gift purchases.","Order value not verified."),
("toom Baumarkt","DE","Intango",550000,0.07,"P",12,"12% (listed)","DIY store, cheap clicks, high rate.","Order value not verified."),
("Groupon","FR","digidip",301000,0.04,"P",7,"7% (digidip observed rate)","$0.04 clicks.","Small baskets."),
("DJI","US","Impact (CyberKick)",246000,0.53,"F",37.5,"5% default × ~$750 (public estimate)","Drones are expensive; 5% default rate in the contract.","Some product lists pay 0–2%; order value estimated."),
("Home Depot","US","Mony Group",30400000,0.14,"F",10.02,"3.2% × ~$313 (public estimate)","30M searches at $0.14 per click.","digidip's real data shows only ~€4.83 per sale, which would need ~13% conversion."),
("The Times","GB","digidip",301000,0.31,"F",21.46,"€19 average actually paid (digidip observed)","Subscription payout observed.","Mostly readers, not buyers."),
("Vrbo","US","CJ (NYJL)",2740000,0.43,"F",27.52,"2% × ~$1,376 booking (public estimate)","2.7M searches, high booking values.","2% rate is low; estimate is rough."),
("Intersport","DE","Intango",301000,0.07,"P",10,"10% (listed)","Sports retailer, cheap clicks.","Order value not verified."),
("Castorama","FR","Intango",2740000,0.07,"P",8,"8% (listed)","DIY, 2.7M searches, $0.07 clicks.","Order value not verified."),
("Lidl","DE","pickalink",11100000,0.05,"P",6.65,"6.65% (listed)","11M searches at $0.05.","Most Lidl searches are about the physical store (flyers)."),
("Target","US","Intango",45500000,0.07,"P",8,"8% (listed)","45M searches at $0.07.","Target pays 1–8% by category; 8% is probably the top category."),
("Flaconi","DE","Intango",550000,0.17,"P",20,"20% (listed)","Beauty retailer with a high rate.","Order value not verified."),
("Office Depot","US","Mony Group",2740000,0.15,"F",9.31,"2.4% × ~$388 (public estimate)","Cheap clicks, large B2B baskets.","Electronics pay only 0.4%."),
("Spartoo","FR","pickalink",201000,0.19,"F",11.69,"fixed €10.41 (lowest listed)","Fixed payout per sale.","Small payout."),
("Temu","CA","pickalink",1000000,0.16,"P",23.27,"23.3% (listed)","High rate, 1M searches.","New users only (typical)."),
("Temu","GB","pickalink",2240000,0.19,"P",23.27,"23.3% (listed)","High rate, 2.2M searches.","New users only (typical)."),
("Temu","AU","pickalink",1000000,0.20,"P",23.27,"23.3% (listed)","High rate, 1M searches.","New users only (typical)."),
("Air Caraïbes","FR","digidip",246000,0.31,"F",16.16,"€14.40 average actually paid (digidip observed)","Real observed payout on flights.","Needs ~10% conversion for 5x."),
("Sling TV","US","Cactus Media",823000,0.60,"F",30,"fixed $30 per lead","Fixed payout, solid volume.","Needs 10% conversion for 5x; lead definition to confirm."),
("Walmart","US","Mony Group",55600000,0.09,"F",4.52,"4% × ~$113 (public estimate)","55M searches at $0.09.","Payout per sale is small; categories pay 0–4%."),
("Depop","US","digidip",1830000,0.10,"F",5.00,"€4.45 average actually paid (digidip observed)","Cheap clicks, real payout data.","Small payout per sale."),
("SHEIN","FR","FlexOffers",3350000,0.14,"F",6.79,"12% new customers × ~$57 (global estimate)","3.4M searches, cheap clicks.","Existing customers pay 0.8%."),
("Temu","US","Intango",5000000,0.14,"P",10,"10–22% (listed)","5M searches.","Rate range wide."),
("Bahn (Deutsche Bahn)","DE","Intango",823000,0.04,"P",4,"4% (listed)","$0.04 clicks for train tickets.","Low rate; many searches are timetable lookups."),
("Micromania","FR","Intango",550000,0.04,"P",4,"4% (listed)","Video-game retailer, $0.04 clicks.","Low rate."),
("West Marine","US","FlexOffers",368000,0.38,"F",16.44,"6% × ~$274 (public estimate)","Large boating baskets.","Needs ~12% conversion for 5x."),
("Vodafone","GB","Intango",673000,0.73,"F",30,"fixed $30 (lowest listed)","Fixed payout per contract.","Needs ~12% conversion."),
("Biocoop","FR","digidip",246000,0.16,"F",6.50,"€5.79 average actually paid (digidip observed)","Real payout data.","Small payout."),
("Qonto","FR","digidip",301000,1.68,"F",67.35,"fixed €60","High fixed payout per business account.","Expensive clicks; B2B."),
("TradingView","US","digidip",1220000,0.87,"F",34.08,"€30.36 average actually paid (digidip observed)","Real observed payout, 1.2M searches.","Many free users searching."),
("La Poste Mobile","FR","pickalink",201000,0.31,"F",11.94,"fixed €10.64 (lowest listed)","Fixed payout.","Small payout."),
("Audible","DE","pickalink",201000,0.39,"F",14.93,"fixed €13.30 (lowest listed)","Fixed payout per trial/subscription.","Needs ~13% conversion."),
("Ubisoft","US","Intango",301000,0.18,"F",6.66,"fixed $6.66 (lowest listed)","Cheap clicks.","Small payout."),
("Expedia","US","digidip",5000000,0.15,"F",5.12,"€4.56 average actually paid (digidip observed)","5M searches, real payout data.","Small average payout."),
("Galeria","DE","Intango",201000,0.10,"P",8,"8% (listed)","Department store, cheap clicks.","Order value not verified."),
("Sally Beauty","US","Shopnomix",2240000,0.11,"P",8,"8% (listed)","2.2M searches, cheap clicks.","Order value not verified."),
("Woot","US","Intango",246000,0.09,"P",7,"7% (listed)","Cheap clicks.","Order value not verified."),
("Fielmann","DE","digidip",823000,0.18,"P",8,"8% (digidip observed rate)","Eyewear: high baskets.","Many searches are for stores/appointments."),
("MediaMarkt","DE","Intango",4090000,0.07,"P",3,"3% (listed)","4M searches, big electronics baskets.","Low rate."),
("eBay","US","digidip",24900000,2.03,"F",550,"fixed up to $550 (top listed tier) — base is 3%","Huge volume.","The $550 is a special bounty; normal payout is ~3% of sale. Expensive clicks."),
("Hugendubel","DE","digidip",450000,0.09,"P",10,"10% (digidip observed rate)","Books, cheap clicks.","Small baskets."),
("Groupon","US","Intango",1500000,0.06,"P",4.5,"4.5–10% (listed)","Cheap clicks.","Small baskets."),
]
assert len(R)==61, len(R)
rows=[]
for i,(b,g,src,sv,cpc,kind,val,basis,why,risk) in enumerate(R,1):
    BULLS=0.65  # Bulls is paid 35% of every payout: we keep 65%
    if kind=="F":
        basis=f"{basis}; ${val:,.2f} payout → ${val*BULLS:,.2f} kept after Bulls 35%"; val=val*BULLS
        be=cpc/val; cr5=5*be; clicks=math.ceil(1/be); bud=min(clicks*cpc,300)
        if clicks*cpc>300: clicks=math.floor(300/cpc)
        rows.append([i,b,g,src,sv,cpc,f"${val:,.2f} kept",basis,f"{cr5*100:.2f}%","",f"${bud:,.0f}",clicks,why,risk])
    else:
        if src=="digidip":  # digidip keeps 30% on % offers: we receive 70% of the listed rate (flat payouts are not reduced)
            basis=f"{basis} → {val*0.7:g}% to us after digidip's 30% share"; val=val*0.7
        basis=f"{basis} → {val*BULLS:.2f}% kept after Bulls 35%"; val=val*BULLS
        need=5*cpc/(0.03*val/100)
        rows.append([i,b,g,src,sv,cpc,"—",basis,"needs order value",f"${need:,.0f}","after order value is known","",why,risk])
hdr=["Rank","Brand","Market","Source","Searches/mo","CPC $","Earn per sale","Payout basis","Conversion needed for 5x ROAS","Order value needed for 5x at 3% conversion","Test budget","Max clicks","Why chosen","Main risk"]
with open("bulls_61_plan.csv","w",newline="") as f:
    w=csv.writer(f); w.writerow(hdr); w.writerows(rows)
def tr(r,first):
    c=["Rank","Brand","Market","Source","Searches/mo","CPC $","Earn per sale","Payout basis","Conv. needed for 5x","Order value needed (if 3% buy)","Budget","Max clicks","Why chosen","Main risk"]
    cells="".join(f"<td>{html.escape(str(x if not isinstance(x,int) or k!=4 else f'{x:,}'))}</td>" for k,x in enumerate(r))
    return f"<tr>{cells}</tr>"
th="".join(f"<th>{h}</th>" for h in ["#","Brand","Market","Source","Searches/mo","CPC","Earn/sale","Payout basis","Conversion needed for 5x","Order value needed (3% conv.)","Budget","Max clicks","Why chosen","Main risk"])
css="""body{font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;color:#111827;max-width:1400px;margin:0 auto;padding:20px}
table{border-collapse:collapse;font-size:12px;width:100%}th,td{border-bottom:1px solid #e5e7eb;padding:6px;text-align:left;vertical-align:top}
th{background:#f8fafc;position:sticky;top:0}h2{margin-top:32px}.note{font-size:13px;color:#374151;background:#f8fafc;padding:10px 14px;border-radius:8px}
td:nth-child(9){font-weight:600}"""
doc=f"""<!doctype html><html><head><meta charset="utf-8"><title>Bulls Test Plan</title><style>{css}</style></head><body>
<h1>Bulls test plan: 11 tests + 50 in queue (target ROAS 5x)</h1>
<p class="note"><b>How offers were found:</b> every offer in your database (CJ, Impact, FlexOffers, Mony, Admitad, Partnerize, Cactus, digidip, Intango, pickalink, Shopnomix, Moonrover — about 290,000 offers),
filtered to brands with ≥200,000 monthly Google searches (DataForSEO, 3 Oct 2026), minus every brand already running in Affise, minus generic-word brands, misspelt domains,
gambling/adult/financial products (Google Ads restrictions) and offers whose % looks like a share of the network's commission rather than of the sale.<br>
<b>Ranking:</b> by the conversion rate needed to reach <b>5x ROAS</b> = 5 × CPC ÷ earnings per sale. Lower is better. Offers where only a % is known (order value unknown) show instead the
<b>order value needed</b> for 5x if 3% of clicks buy.<br>
<b>Test budget:</b> enough clicks to expect 5 sales if the offer really converts at the 5x level (≈ one payout), capped at $300.
If it gets 0 sales by half the clicks, pause: an offer that truly converts at the 5x level gets 0 sales in that window only ~8% of the time.<br>
<b>Bulls share:</b> every payout is reduced by the 35% paid to Bulls; all numbers below use what you keep (65%). 5x ROAS is measured on that kept amount.<br><b>digidip:</b> on % offers digidip keeps 30%, so the rate used is 70% of the listed rate; flat payouts are used in full.<br><b>Scale only if:</b> ROAS ≥ 5x with at least 3 confirmed sales. EUR→USD at 1.1225 (ECB, 2 Oct 2026). Nothing here has been launched.</p>
<h2>Test now (1–11)</h2><table><tr>{th}</tr>{''.join(tr(r,True) for r in rows[:11])}</table>
<h2>Queue (12–61), in order</h2><table><tr>{th}</tr>{''.join(tr(r,False) for r in rows[11:])}</table>
<p class="note"><b>Honest read on 5x:</b> only about 10 offers need ≤5% conversion to hit 5x ROAS. From roughly #36 onward, the required conversion rate is above 10%,
which brand-search traffic rarely reaches; those stay in the queue only if the first tests show unexpectedly high conversion. Every "Main risk" must be checked before launch,
plus brand-bidding permission and tracking links for each brand.</p></body></html>"""
open("bulls_61_plan.html","w").write(doc)
for r in rows[:14]: print(r[0],r[1],r[2],r[8],r[9],r[10])
