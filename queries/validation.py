"""Independent source oracle and strict result validators; never execute a workload."""
from collections import Counter
from decimal import Decimal, ROUND_HALF_EVEN, ROUND_HALF_UP, localcontext
from fractions import Fraction

from src.dataset.model import DataError, timestamp, validate_order, valid_uuid
from .definitions import QueryBlocked

BOUNDARY = timestamp('2026-01-01T00:00:00Z')


def number(value):
    if type(value) not in (int, Decimal) or not Decimal(value).is_finite():
        raise ValueError('Expected finite exact numeric value, never float/string/bool')
    return Decimal(value)


def source_reference(docs, query):
    if query not in ('Q1', 'Q2'):
        raise QueryBlocked('Unknown source query')
    groups = {}
    eligible = {}
    seen = set()
    for doc in docs:
        if query == 'Q2' and 'final_total' not in doc.get('payment', {}):
            raise QueryBlocked('Q2 incompatible with totals-only: payment.final_total is missing')
        try:
            layout = 'totals-and-alias' if 'final_total' in doc['payment'] else 'totals-only'
            validate_order(doc, layout)
            uid = valid_uuid(doc['order_id'])
        except (DataError, KeyError) as exc:
            raise QueryBlocked('Source schema/type/date/alias invalid: ' + str(exc)) from exc
        if uid in seen:
            raise QueryBlocked('Duplicate source UUID')
        seen.add(uid)
        if query == 'Q1':
            for item in doc['items']:
                # Integer cents and rational arithmetic independent of Mongo/SQL expressions.
                price_cents = int(number(item['price']) * 100)
                if price_cents <= 5000:
                    continue
                key = (doc['customer']['geo']['country'], item['category'])
                cents, count = groups.get(key, (0, 0))
                groups[key] = (cents + price_cents * item['qty'], count + 1)
        elif query == 'Q2':
            if doc['payment']['status'] == 'completed' and timestamp(doc['timestamp']) >= BOUNDARY:
                eligible[uid] = {'order_id': uid, 'customer_id': doc['customer']['id'],
                                 'final_total': number(doc['payment']['final_total'])}
        else:
            raise QueryBlocked('Unknown query')
    if query == 'Q1':
        return {'query': 'Q1', 'groups': groups}
    k = min(1000, len(eligible))
    counts = Counter(row['final_total'] for row in eligible.values())
    cutoff = sorted((row['final_total'] for row in eligible.values()), reverse=True)[k-1] if k else None
    mandatory = {uid for uid, row in eligible.items() if cutoff is not None and row['final_total'] > cutoff}
    ties = {uid for uid, row in eligible.items() if cutoff is not None and row['final_total'] == cutoff}
    return {'query': 'Q2', 'eligible': eligible, 'k': k, 'cutoff': cutoff,
            'mandatory': mandatory, 'ties': ties, 'tie_slots': k-len(mandatory),
            'boundary_tie': len(ties) > k-len(mandatory),
            'repeated_total_values': sum(n > 1 for n in counts.values())}


def _plain(value):
    if isinstance(value, (tuple, list)):
        return [_plain(v) for v in value]
    if isinstance(value, dict):
        return {str(k):_plain(v) for k,v in value.items()}
    return value


def failure(engine, query, field, expected, obtained, cause):
    return {'status': 'FAIL', 'engine': engine, 'query': query, 'field': field,
            'expected': _plain(expected), 'obtained': _plain(obtained), 'possible_cause': cause}


def normalize_q1(rows, engine):
    result = {}
    for row in rows:
        country = row['_id']['country'] if engine == 'mongo' else row['country']
        category = row['_id']['category'] if engine == 'mongo' else row['category']
        if not isinstance(country, str) or not isinstance(category, str):
            raise ValueError('Group keys must be strings')
        key = (country, category)
        if key in result:
            raise ValueError('Repeated result group')
        count = row['count']
        if type(count) is not int or count <= 0:
            raise ValueError('Invalid group count')
        result[key] = {'count': count, 'total_revenue': number(row['total_revenue']),
                       'avg_revenue': number(row['avg_revenue'])}
    return result


def _average_valid(value, exact, engine):
    if Fraction(value) == exact:
        return True, 'exact rational value'
    # Not epsilon matching. Require rounded exact rational at the engine's returned quantum,
    # with at least the documented minimum significant precision of the representation.
    minimum = 34 if engine == 'mongo' else 16
    if len(value.as_tuple().digits) < minimum:
        return False, f'Non-exact average has fewer than {minimum} significant digits'
    rounding = ROUND_HALF_EVEN if engine == 'mongo' else ROUND_HALF_UP
    quantum = Decimal(1).scaleb(value.as_tuple().exponent)
    with localcontext() as context:
        context.prec = max(120, len(value.as_tuple().digits) + 40)
        expected = (Decimal(exact.numerator) / Decimal(exact.denominator)).quantize(quantum, rounding=rounding)
    return value == expected, f'{rounding} of exact rational at returned quantum {quantum}'


def validate_q1(reference, rows, engine):
    try:
        actual = normalize_q1(rows, engine)
    except (KeyError, TypeError, ValueError) as exc:
        return failure(engine, 'Q1', 'result_structure', 'unique groups with exact numeric types', str(exc), 'projection/type conversion or duplicated groups')
    if set(actual) != set(reference['groups']):
        return failure(engine, 'Q1', 'groups', sorted(reference['groups']), sorted(actual), 'unwind/filter/group differs')
    precision_notes = []
    for key, (cents, count) in reference['groups'].items():
        current = actual[key]
        total = Decimal(cents).scaleb(-2)
        if current['count'] != count:
            return failure(engine, 'Q1', f'{key}.count', count, current['count'], 'count items after strict price > 50, not orders')
        if current['total_revenue'] != total:
            return failure(engine, 'Q1', f'{key}.total_revenue', total, current['total_revenue'], 'qty*price, precision loss or incorrect filtering')
        rational = Fraction(cents, 100*count)
        good, reason = _average_valid(current['avg_revenue'], rational, engine)
        if not good:
            return failure(engine, 'Q1', f'{key}.avg_revenue', str(rational), current['avg_revenue'], reason)
        if Fraction(current['avg_revenue']) != rational:
            precision_notes.append({'group': list(key), 'exact_fraction': str(rational),
                                    'obtained': current['avg_revenue'], 'justification': reason})
    return {'status': 'PASS', 'engine': engine, 'query': 'Q1', 'groups': len(actual),
            'average_precision_notes': precision_notes}


def normalize_q2(rows, engine):
    result = []
    for row in rows:
        uid = valid_uuid(row['order_id'])
        customer = row['customer']['id'] if engine == 'mongo' else row['customer_id']
        valid_uuid(customer)
        total = row['payment']['final_total'] if engine == 'mongo' else row['final_total']
        result.append({'order_id': uid, 'customer_id': customer, 'final_total': number(total)})
    return result


def validate_q2(reference, rows, engine):
    try:
        actual = normalize_q2(rows, engine)
    except (KeyError, TypeError, ValueError) as exc:
        return failure(engine, 'Q2', 'projection/types', 'order_id/customer.id/final_total', str(exc), 'projection or lost numeric/UUID types')
    if len(actual) != reference['k']:
        return failure(engine, 'Q2', 'row_count', reference['k'], len(actual), 'filter, boundary or LIMIT 1000 differs')
    chosen = set()
    previous = None
    for row in actual:
        uid, value = row['order_id'], row['final_total']
        if uid in chosen:
            return failure(engine, 'Q2', 'order_id', 'unique UUIDs', uid, 'duplicate result')
        chosen.add(uid)
        if previous is not None and value > previous:
            return failure(engine, 'Q2', 'order', 'descending final_total', value, 'sort direction or numeric/string ordering')
        previous = value
        expected = reference['eligible'].get(uid)
        if expected is None:
            return failure(engine, 'Q2', 'eligibility', 'completed and timestamp >= boundary', uid, 'status/date filter differs')
        for key in ('customer_id', 'final_total'):
            if row[key] != expected[key]:
                return failure(engine, 'Q2', f'{uid}.{key}', expected[key], row[key], 'projection, alias or precision differs')
        if value < reference['cutoff']:
            return failure(engine, 'Q2', 'Top-K threshold', reference['cutoff'], value, 'a lower row displaced an eligible higher result')
    if not reference['mandatory'] <= chosen:
        return failure(engine, 'Q2', 'mandatory_UUIDs', sorted(reference['mandatory']-chosen), [], 'missing rows strictly above cutoff')
    return {'status': 'PASS', 'engine': engine, 'query': 'Q2', 'rows': len(actual),
            'cutoff': reference['cutoff'], 'boundary_tie': reference['boundary_tie'],
            'tied_at_cutoff': len(reference['ties']), 'available_tie_slots': reference['tie_slots'],
            'repeated_total_values': reference['repeated_total_values']}


def compare_results(reference, results):
    """results maps engine -> rows. All comparisons anchored to the independent source."""
    checks = {engine: (validate_q1 if reference['query']=='Q1' else validate_q2)(reference, rows, engine)
              for engine, rows in results.items()}
    failed = any(c['status'] == 'FAIL' for c in checks.values())
    complete = set(results) == {'mongo', 'postgres'}
    report = {'status': 'FAIL' if failed else 'PASS' if complete else 'BLOCKED', 'query': reference['query'],
              'checks': checks, 'cross_engine': 'compared' if complete else 'requires real results from both engines'}
    if complete and not failed and reference['query'] == 'Q2':
        left = {r['order_id'] for r in normalize_q2(results['mongo'], 'mongo')}
        right = {r['order_id'] for r in normalize_q2(results['postgres'], 'postgres')}
        report['different_UUIDs_due_to_boundary_tie'] = len(left ^ right)
        report['tie_explanation'] = 'only arbitrary selection at cutoff is permitted; all higher UUIDs required'
    return report
