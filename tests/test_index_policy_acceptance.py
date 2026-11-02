"""Operator acknowledgement is not a substitute for a valid physical index."""
import unittest
from copy import deepcopy

from queries.indexes import audit_postgres, audit_mongo
from benchmark.preflight import index_policy_decision, PG_INDEX_ACK_EXACT


def postgres_inventory():
    return [
        {'name': 'orders_pkey', 'access_method': 'btree', 'valid': True,
         'ready': True, 'nkeys': 1, 'natts': 1, 'predicate': None,
         'primary': True, 'unique': True, 'columns': ['id'],
         'expression': None},
        {'name': 'orders_timestamp_text_idx', 'access_method': 'btree',
         'valid': True, 'ready': True, 'nkeys': 1, 'natts': 1,
         'predicate': None, 'primary': False, 'unique': False,
         'columns': None, 'expression': "(data ->> 'timestamp'::text)"},
    ]


class IndexPolicyTests(unittest.TestCase):
    def test_original_postgres_audit_remains_academically_blocked(self):
        audit = audit_postgres(postgres_inventory())
        self.assertEqual(audit['physical_index_status'], 'PASS')
        self.assertEqual(audit['status'], 'BLOCKED')

    def test_requires_explicit_correct_acceptance(self):
        audit = audit_postgres(postgres_inventory())
        for ack in (None, '', 'yes', 'ACCEPT', PG_INDEX_ACK_EXACT + '!'):
            self.assertEqual(index_policy_decision('postgres', audit, ack)['status'], 'BLOCKED')
        accepted = index_policy_decision('postgres', audit, PG_INDEX_ACK_EXACT)
        self.assertEqual(accepted['status'], 'PASS')
        self.assertTrue(accepted['operator_acknowledged'])
        self.assertFalse(accepted['original_q2_cast_matches_text_index'])
        self.assertEqual(accepted['teacher_approval'], 'not_asserted')
        self.assertEqual(accepted['q2_index_usage_from_explain'], 'not_verified_by_this_gate')

    def test_bad_postgres_indexes_cannot_be_overridden(self):
        rows = postgres_inventory()
        cases = []
        cases.append(rows[:1])                             # no timestamp index
        cases.append(rows[1:])                             # no PK
        extra = deepcopy(rows); extra.append(deepcopy(rows[1])); cases.append(extra)
        invalid = deepcopy(rows); invalid[1]['valid'] = False; cases.append(invalid)
        unready = deepcopy(rows); unready[1]['ready'] = False; cases.append(unready)
        partial = deepcopy(rows); partial[1]['predicate'] = 'x'; cases.append(partial)
        wrong_expr = deepcopy(rows); wrong_expr[1]['expression'] = "data->>'other'"; cases.append(wrong_expr)
        wrong_am = deepcopy(rows); wrong_am[1]['access_method'] = 'hash'; cases.append(wrong_am)
        for case in cases:
            with self.subTest(case=case):
                audit = audit_postgres(case)
                self.assertEqual(audit['physical_index_status'], 'BLOCKED')
                self.assertEqual(index_policy_decision('postgres', audit, PG_INDEX_ACK_EXACT)['status'], 'BLOCKED')

    def test_mongodb_keeps_its_existing_strict_gate(self):
        mongo = [{ 'key': {'_id': 1}}, {'key': {'timestamp': 1}}, {'key': {'order_id': 1}}]
        good = audit_mongo(mongo)
        self.assertEqual(index_policy_decision('mongo', good)['status'], 'PASS')
        bad = audit_mongo(mongo[:1])
        self.assertEqual(index_policy_decision('mongo', bad, PG_INDEX_ACK_EXACT)['status'], 'BLOCKED')


if __name__ == '__main__':
    unittest.main()
