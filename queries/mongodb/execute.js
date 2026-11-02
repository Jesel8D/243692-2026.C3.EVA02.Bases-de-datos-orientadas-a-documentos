// Local mongosh collection API; credentials remain in container environment.
const fs = require('fs');
const p = JSON.parse(fs.readFileSync(0, 'utf8'));
const conn = new Mongo('mongodb://127.0.0.1:27017');
const admin = conn.getDB('admin');
if (!admin.auth(process.env.MONGO_INITDB_ROOT_USERNAME, process.env.MONGO_INITDB_ROOT_PASSWORD)) throw new Error('Authentication failed');
const database = conn.getDB(process.env.DATA_DATABASE_NAME);
const c = database.getCollection('orders');
let result;
if (p.action === 'preflight') {
  const orderTypes = c.aggregate([{$group:{_id:{timestamp:{$type:'$timestamp'},final_total:{$type:'$payment.final_total'},totals_final_total:{$type:'$payment.totals.final_total'},status:{$type:'$payment.status'},order_id:{$type:'$order_id'},customer_id:{$type:'$customer.id'}},n:{$sum:1}}}], {maxTimeMS:p.timeout_ms}).toArray();
  const itemTypes = c.aggregate([{$unwind:'$items'},{$group:{_id:{qty:{$type:'$items.qty'},price:{$type:'$items.price'}},n:{$sum:1}}}], {maxTimeMS:p.timeout_ms}).toArray();
  let invalidDates = 0;
  const dates = c.find({}, {timestamp:1}).maxTimeMS(p.timeout_ms);
  while (dates.hasNext()) {
    const t = dates.next().timestamp;
    try {
      if (typeof t !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(t) || new Date(t).toISOString().replace('.000Z','Z') !== t) invalidDates++;
    } catch (_) { invalidDates++; }
  }
  result = {count:c.countDocuments({}, {maxTimeMS:p.timeout_ms}),order_types:orderTypes.map(x=>({...x._id,n:x.n})),item_types:itemTypes.map(x=>({...x._id,n:x.n})),invalid_timestamps:invalidDates,invalid_qty:c.countDocuments({items:{$elemMatch:{qty:{$nin:[1,2,3,4,5,6]}}}}, {maxTimeMS:p.timeout_ms}),invalid_alias:c.countDocuments({$expr:{$ne:['$payment.final_total','$payment.totals.final_total']}}, {maxTimeMS:p.timeout_ms})};
} else if (p.action === 'run' || p.action === 'explain') {
  const options = {...p.options, maxTimeMS:p.timeout_ms};
  const effective = {server_version:database.version(),options:options};
  if (p.action === 'run') result = {effective:effective,rows:c.aggregate(p.pipeline, options).toArray()};
  else result = {effective:effective,plan:c.explain('executionStats').aggregate(p.pipeline, options)};
} else if (p.action === 'indexes' || p.action === 'prepare_indexes') {
  let indexes;
  try { indexes = c.getIndexes(); } catch (e) { if (e.code === 26) indexes=[]; else throw e; }
  const allowed = x => JSON.stringify(x.key) === '{"_id":1}' || JSON.stringify(x.key) === '{"timestamp":1}' || JSON.stringify(x.key) === '{"order_id":1}';
  if (p.action === 'prepare_indexes') {
    if (indexes.some(x=>!allowed(x) || x.sparse || x.partialFilterExpression || x.expireAfterSeconds !== undefined || x.collation || (x.unique && JSON.stringify(x.key)!=='{"_id":1}'))) throw new Error('Unexpected indexes: no automatic deletion/replacement');
    if (!indexes.some(x=>JSON.stringify(x.key)==='{"timestamp":1}')) c.createIndex({timestamp:1}, {name:'orders_timestamp_idx',maxTimeMS:p.timeout_ms});
    if (!indexes.some(x=>JSON.stringify(x.key)==='{"order_id":1}')) c.createIndex({order_id:1}, {name:'orders_order_id_idx',maxTimeMS:p.timeout_ms});
    indexes = c.getIndexes();
  }
  result = indexes;
} else throw new Error('Unsupported action');
print(EJSON.stringify(result, {relaxed:false}));
