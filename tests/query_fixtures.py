"""Controlled data for correctness tests only, never performance evidence."""
from copy import deepcopy
from decimal import Decimal
import uuid
from src.dataset.files import configuration
from src.dataset.model import documents, totals, validate_order, LOCATIONS


def _items(doc, prices):
    template = doc['items'][0]
    result = []
    for price, qty, category in prices:
        item = deepcopy(template)
        item.update(price=Decimal(price),qty=qty,category=category,tax_pct=Decimal('0.00'),discounts=[])
        result.append(item)
    doc['items'] = result


def _finish(doc):
    doc['payment']['totals'] = totals(doc['items'])
    doc['payment']['final_total'] = doc['payment']['totals']['final_total']
    validate_order(doc)
    return doc


def controlled():
    c = configuration(count=10)
    docs = list(documents(c['seed'],10,c['start'],c['end'],c['payment_layout']))
    for d in docs:
        loc = LOCATIONS[0]
        d['customer']['geo'].update(country=loc[0],state=loc[1],city=loc[2],zip=loc[3],coordinates=[Decimal(loc[4]),Decimal(loc[5])])
        d['timestamp']='2026-01-01T00:00:00Z'
        d['payment']['status']='pending'
        _items(d,[('0.01',1,'books')])
    _items(docs[0],[('49.99',2,'electronics'),('50.00',3,'electronics'),('50.01',2,'electronics')])
    _items(docs[1],[('50.02',1,'electronics'),('50.02',1,'electronics')])
    _items(docs[2],[('60.10',3,'books')])
    _items(docs[3],[('80.25',4,'electronics')])
    # Q1 must ignore these payment adjustments.
    docs[3]['items'][0]['tax_pct']=Decimal('16.00')
    docs[3]['items'][0]['discounts']=[Decimal('1.00')]
    loc = LOCATIONS[1]
    docs[3]['customer']['geo'].update(country=loc[0],state=loc[1],city=loc[2],zip=loc[3],coordinates=[Decimal(loc[4]),Decimal(loc[5])])
    for i in (4,5):
        _items(docs[i],[('50.00',1,'books')])
    for i in (0,1,3,4,5,9):
        docs[i]['payment']['status']='completed'
    docs[0]['timestamp']='2025-12-31T23:59:59Z'
    docs[3]['timestamp']='2026-01-01T00:00:01Z'
    docs[5]['timestamp']='2026-06-01T00:00:00Z'
    docs[6]['payment']['status']='failed'
    docs[7]['payment']['status']='refunded'
    return [_finish(d) for d in docs]


def boundary_ties():
    base = controlled()[1]
    docs = []
    for i in range(1005):
        d = deepcopy(base)
        d['order_id']=str(uuid.uuid5(uuid.NAMESPACE_URL, f'phase3-tie-order:{i}'))
        d['payment']['transaction_id']=str(uuid.uuid5(uuid.NAMESPACE_URL, f'phase3-tie-transaction:{i}'))
        _items(d,[('200.00' if i<2 else '50.00' if i==1004 else '100.00',1,'books')])
        docs.append(_finish(d))
    return docs
