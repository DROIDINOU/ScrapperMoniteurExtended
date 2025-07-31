import csv

def read_hudoc_csv(csv_filename):
    with open(csv_filename, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"\n✅ {len(rows)} documents chargés.\n")

    for i, row in enumerate(rows, start=1):
        print(f"{i}. {row['title']}")
        print(f"   URL : {row['url']}")
        print(f"   itemid : {row['itemid']}\n")


if __name__ == "__main__":
    read_hudoc_csv("hudoc_all_documents.csv")
