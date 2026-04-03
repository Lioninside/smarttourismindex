import pandas as pd
import re

MASTER_FILE = "places_master.csv"
OUTPUT_FILTERED = "places_master_bfs.csv"
OUTPUT_MISSING = "places_not_in_bfs.csv"


# === BFS LIST (paste as Python list) ===
bfs_list = [
"Kloten","Opfikon","Dübendorf","Uster","Winterthur","Zürich","Wädenswil","Horgen",
"Langenthal","Bern","Köniz","Biel/Bienne","Burgdorf","Adelboden","Aeschi bei Spiez",
"Kandersteg","Reichenbach im Kandertal","Beatenberg","Brienz (BE)","Grindelwald",
"Interlaken","Lauterbrunnen","Matten bei Interlaken","Unterseen","Wilderswil",
"Moutier (BE)","Diemtigen","Spiez","Hasliberg","Innertkirchen","Meiringen","Lenk",
"Saanen","Langnau im Emmental","Schangnau","Sigriswil","Thun","Herzogenbuchsee",
"Emmen","Kriens","Luzern","Meggen","Vitznau","Weggis","Sursee","Andermatt",
"Gurtnellen","Einsiedeln","Feusisberg","Freienbach","Küssnacht (SZ)","Ingenbohl",
"Morschach","Schwyz","Engelberg","Sachseln","Sarnen","Beckenried","Emmetten",
"Glarus Nord","Glarus Süd","Unterägeri","Zug","Haut-Intyamon","Bulle","Gruyères",
"Fribourg","Murten","Plaffeien","Egerkingen","Grenchen","Olten","Solothurn","Basel",
"Liestal","Pratteln","Schaffhausen","Hundwil","Gais","Teufen (AR)","Heiden",
"Appenzell","Gonten","St. Gallen","Rorschacherberg","Altstätten","Buchs (SG)",
"Bad Ragaz","Flums","Quarten","Walenstadt","Amden","Rapperswil-Jona",
"Eschenbach (SG)","Wildhaus-Alt St. Johann","Neckertal","Uzwil","Wil (SG)",
"Vaz/Obervaz","Surses","Poschiavo","Laax","Vals","Lumnezia","Ilanz/Glion",
"Rheinwald","Flims","Zernez","Samnaun","Scuol","Celerina/Schlarigna","Pontresina",
"Samedan","St. Moritz","Bregaglia","Val Müstair","Davos","Klosters","Chur","Arosa",
"Maienfeld","Breil/Brigels","Tujetsch","Aarau","Baden","Lenzburg","Rheinfelden",
"Zofingen","Arbon","Frauenfeld","Kreuzlingen","Bellinzona","Ascona","Locarno",
"Muralto","Lugano","Paradiso","Collina d'Oro","Monteceneri","Chiasso","Mendrisio",
"Leysin","Ollon","Ormont-Dessus","Bullet","Lausanne","Bourg-en-Lavaux","Morges",
"Nyon","Château-d'Oex","Le Chenit","Montreux","Vevey","Blonay - Saint-Légier",
"Yverdon-les-Bains","Brig-Glis","Nendaz","Orsières","Val de Bagnes","Goms",
"Evolène","Leukerbad","Martigny","Champéry","Saint-Maurice","Sierre","Anniviers",
"Crans-Montana","Sion","Saas-Fee","Saas-Grund","Visp","Zermatt",
"La Grande Béroche","La Chaux-de-Fonds","Neuchâtel","Laténa","Genève","Lancy",
"Meyrin","Vernier","Delémont","Saignelégier","Porrentruy","Clos du Doubs",
"Moutier (JU)"
]


# === NORMALIZATION ===
def normalize(name):
    if pd.isna(name):
        return ""
    name = str(name).lower().strip()

    # remove canton in brackets
    name = re.sub(r"\s*\(.*?\)", "", name)

    # normalize umlauts
    replacements = {
        "ä": "a", "ö": "o", "ü": "u",
        "é": "e", "è": "e", "à": "a"
    }
    for k, v in replacements.items():
        name = name.replace(k, v)

    return name.strip()


# === LOAD MASTER ===
master = pd.read_csv(MASTER_FILE)
master["name_norm"] = master["name"].apply(normalize)

# === PREP BFS ===
bfs_df = pd.DataFrame({"name": bfs_list})
bfs_df["name_norm"] = bfs_df["name"].apply(normalize)

bfs_set = set(bfs_df["name_norm"])

# === FILTER ===
master["in_bfs"] = master["name_norm"].isin(bfs_set)

filtered = master[master["in_bfs"]].copy()
missing = master[~master["in_bfs"]].copy()

# === OUTPUT ===
filtered.drop(columns=["name_norm", "in_bfs"]).to_csv(OUTPUT_FILTERED, index=False)
missing.drop(columns=["name_norm", "in_bfs"]).to_csv(OUTPUT_MISSING, index=False)

print("\n=== RESULT ===")
print(f"Master total: {len(master)}")
print(f"In BFS: {len(filtered)}")
print(f"Not in BFS: {len(missing)}")

print("\n=== NOT IN BFS ===")
print(missing["name"].to_string(index=False))