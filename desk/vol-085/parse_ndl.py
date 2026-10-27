import json, re, sys

path = sys.argv[1]
data = json.load(open(path))
for url, res in data.items():
    body = res['body']
    items = re.split(r'<item>', body)[1:]
    print('=== QUERY', url, '===', len(items), 'items')
    for it in items:
        isbn_m = re.search(r'dcndl:ISBN\">([^<]+)</dc:identifier>', it)
        if isbn_m:
            title_m = re.search(r'<dc:title>([^<]*)</dc:title>', it)
            creator_m = re.search(r'<dc:creator>([^<]*)</dc:creator>', it)
            date_m = re.search(r'<dcterms:issued>([^<]*)</dcterms:issued>', it)
            pub_m = re.search(r'<dc:publisher>([^<]*)</dc:publisher>', it)
            link_m = re.search(r'<link>([^<]*)</link>', it)
            print('ISBN:', isbn_m.group(1), '| title:', title_m.group(1) if title_m else None, '| creator:', creator_m.group(1) if creator_m else None, '| pub:', pub_m.group(1) if pub_m else None, '| date:', date_m.group(1) if date_m else None, '| link:', link_m.group(1) if link_m else None)
