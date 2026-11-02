"""Keep raw plans and scoped summaries; unavailable is null, never fabricated zero."""
from decimal import Decimal


def _diagnostic(value):
    if isinstance(value, dict) and len(value)==1:
        k = next(iter(value))
        if k in ('$numberInt','$numberLong'):
            return int(value[k])
        if k in ('$numberDouble','$numberDecimal'):
            return Decimal(value[k])
    return value


def summarize_plan(plan, engine):
    nodes = []
    def walk(value, path):
        if isinstance(value, list):
            for i, child in enumerate(value):
                walk(child, path + [str(i)])
        elif isinstance(value, dict):
            if engine=='postgres' and 'Node Type' in value:
                keys = ['Node Type','Relation Name','Index Name','Actual Rows','Actual Loops','Sort Method',
                        'Sort Space Used','Sort Space Type','Peak Memory Usage','HashAgg Batches',
                        'Temp Read Blocks','Temp Written Blocks','Shared Read Blocks','Shared Hit Blocks']
                nodes.append({'path':'.'.join(path), **{k:value.get(k) for k in keys}})
            elif engine=='mongo' and any(k in value for k in ('stage','$sort','$group','totalDocsExamined','usedDisk')):
                keys = ['stage','nReturned','totalDocsExamined','totalKeysExamined','docsExamined','keysExamined',
                        'usedDisk','spills','spilledRecords','totalDataSizeSortedBytesEstimate','maxAccumulatorMemoryUsageBytes']
                nodes.append({'path':'.'.join(path), **{k:_diagnostic(value.get(k)) for k in keys}})
            for key, child in value.items():
                walk(child, path + [key])
    walk(plan, [])
    return {'engine':engine,'nodes':nodes,'unavailable_value':None,
            'units':'native engine fields (PG sort space KiB, blocks native block units); see raw plan',
            'warning':'EXPLAIN executes query; times are diagnostic, not benchmark latency'}
