from typing import Tuple
from df.common import pipe
from df.itools import ibefore, iafter, igroup, ifile
from urllib.request import Request, urlopen

latests = {}

import re

class WCOEndpoint:
    def __init__(self, baseSite: str, blockMatch: Tuple[bytes, bytes], itemMatch: Tuple[bytes, bytes]):
        self.baseSite = baseSite
        self.blockMatch = blockMatch
        self.itemMatch = itemMatch

ENDPOINTS = [
    WCOEndpoint(
        'https://www.wco.tv/anime/',
        (b'id="sidebar_right3"', b'</div></div>'),
        (b'<div class="cat-eps">', b'</div>')
    ),
    WCOEndpoint(
        'https://www.wcostream.net/anime/',
        (b'id="catlist-listview"', b'</div>'),
        (b'<li>', b'</li>')
    )
]

def checkPage(page, latest_list=latests, endpoint=ENDPOINTS[1]):
    link = endpoint.baseSite + page
    if page in latest_list:
        latest = latest_list[page]
    else:
        latest = ''

    req = Request(
        link,
        headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36'
        }
    )
    with urlopen(req) as f:
        processor = pipe(
            igroup(*endpoint.itemMatch),
            ibefore(endpoint.blockMatch[1]), # Order is important, you want to cut only first target AFTER start
            iafter(endpoint.blockMatch[0])
        )
        it = processor(ifile(f))
        reHRef = re.compile(b'href="([^"]*)"')
        reTitle = re.compile(b'title="([^"]*)"')
        first = True
        for el in it:
            title = reTitle.search(el)[1].decode('utf-8')
            href = reHRef.search(el)[1].decode('utf-8')
            if first:
                latest_list[page] = href
                first = False
            if href == latest:
                break
            yield (title, href)

if __name__ == '__main__':
    for title, _ in checkPage('black-clover-english-subbed'):
        print(title)
