"""Stdlib adapters via existing containers. No ports, external drivers or secrets on host."""
import csv
from decimal import Decimal
import io
import os
import re
import subprocess

from .model import DataError, json_text, parse_json, valid_uuid

MONGO_SCRIPT = r'''
const fs = require('fs');
const conn = new Mongo('mongodb://127.0.0.1:27017');
const admin = conn.getDB('admin');
if (!admin.auth(process.env.MONGO_INITDB_ROOT_USERNAME, process.env.MONGO_INITDB_ROOT_PASSWORD)) throw new Error('Authentication failed');
const database = conn.getDB(process.env.DATA_DATABASE_NAME);
const collection = database.getCollection('orders');
function readStdinFully() {
  const chunks = [];
  const buffer = Buffer.allocUnsafe(65536);
  const sleeper = new Int32Array(new SharedArrayBuffer(4));
  const deadline = Date.now() + 110000;

  while (true) {
    let bytesRead;

    try {
      bytesRead = fs.readSync(
        0, buffer, 0, buffer.length, null
      );
    } catch (error) {
      if (
        error.code === 'EAGAIN' ||
        error.code === 'EWOULDBLOCK'
      ) {
        if (Date.now() >= deadline) {
          throw new Error('Timeout reading stdin');
        }

        Atomics.wait(sleeper, 0, 0, 10);
        continue;
      }

      throw error;
    }

    if (bytesRead === 0) {
      break;
    }

    chunks.push(Buffer.from(buffer.subarray(0, bytesRead)));
  }

  return Buffer.concat(chunks).toString('utf8');
}

const payload = EJSON.parse(
  readStdinFully(),
  {relaxed:false}
);
let result;
if (payload.operation === 'count') {
  result = collection.countDocuments({});
} else if (payload.operation === 'fetch') {
  result = collection.find({order_id:{$in:payload.ids}}).toArray();
} else if (payload.operation === 'insert') {
  const r = collection.insertMany(payload.docs, {ordered:true});
  result = Object.keys(r.insertedIds).length;
} else { throw new Error('Unsupported operation'); }
print(EJSON.stringify(result, {relaxed:false}));
'''


def to_ejson(value):
    if isinstance(value, Decimal):
        return {"$numberDecimal": format(value, "f")}
    if isinstance(value, list):
        return [to_ejson(v) for v in value]
    if isinstance(value, dict):
        return {k: to_ejson(v) for k, v in value.items()}
    return value


def from_ejson(value):
    if isinstance(value, list):
        return [from_ejson(v) for v in value]
    if isinstance(value, dict):
        if set(value) == {"$numberDecimal"}:
            return Decimal(value["$numberDecimal"])
        if set(value) in ({"$numberInt"}, {"$numberLong"}):
            return int(next(iter(value.values())))
        if set(value) == {"$numberDouble"}:
            raise DataError("Unexpected binary-double BSON value; cannot claim exact contract")
        return {k: from_ejson(v) for k, v in value.items()}
    return value


class DockerAdapter:
    def __init__(self, engine, timeout=120):
        self.engine = engine
        self.container = os.environ.get("DATA_MONGO_CONTAINER" if engine == "mongo" else "DATA_PG_CONTAINER", "")
        self.database = os.environ.get("DATA_DATABASE_NAME", "")
        self.timeout = timeout
        if not re.fullmatch(r"[a-f0-9]{12,64}", self.container):
            raise DataError("Missing container ID: use scripts/import_* or scripts/compare_data.sh")
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", self.database):
            raise DataError("Invalid/missing DATA_DATABASE_NAME")

    def execute(self, command, data):
        env = os.environ.copy()
        for name in ("DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH"):
            env.pop(name, None)
        cmd = ["docker", "--host=unix:///var/run/docker.sock", "exec", "-i", "-e",
               "DATA_DATABASE_NAME=" + self.database, self.container, *command]
        try:
            done = subprocess.run(cmd, input=data, text=True, encoding="utf8", capture_output=True,
                                  timeout=self.timeout, env=env, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise DataError(f"{self.engine}: command unavailable/timed out; check container and retained partial load") from exc
        if done.returncode:
            # Server diagnostics may echo records/passwords. Do not dump them into reports.
            raise DataError(f"{self.engine}: database command failed (exit {done.returncode}); inspect locally. No existing rows were replaced; batches may already be committed")
        return done.stdout.strip()


class MongoAdapter(DockerAdapter):
    def __init__(self, timeout=120):
        super().__init__("mongo", timeout)

    def command(self, operation, **values):
        output = self.execute(["mongosh", "--quiet", "--norc", "--eval", MONGO_SCRIPT],
                              json_text(to_ejson({"operation": operation, **values})))
        return from_ejson(parse_json(output))

    def ensure(self):
        # Collection is created only by first insertion; _id has its native unique index.
        pass

    def count(self):
        return self.command("count")

    def fetch(self, ids):
        records = self.command("fetch", ids=ids)
        result = {}
        for row in records:
            uid = valid_uuid(row.get("order_id"))
            if row.pop("_id", None) != uid or uid in result:
                raise DataError("MongoDB duplicate order_id or inconsistent technical _id")
            result[uid] = row
        return result

    def insert(self, docs):
        records = [{**doc, "_id": doc["order_id"]} for doc in docs]
        if self.command("insert", docs=records) != len(records):
            raise DataError("MongoDB inserted count differs")


class PostgresAdapter(DockerAdapter):
    def __init__(self, timeout=120):
        super().__init__("postgres", timeout)

    def sql(self, sql):
        return self.execute(["sh", "-c", 'PGPASSWORD="$POSTGRES_PASSWORD" exec psql -X -qAt -h 127.0.0.1 -U "$POSTGRES_USER" -d "$DATA_DATABASE_NAME" -v ON_ERROR_STOP=1'], sql)

    def ensure(self):
        self.sql("CREATE TABLE IF NOT EXISTS public.orders (id UUID PRIMARY KEY, data JSONB NOT NULL);\n")
        columns = self.sql("SELECT column_name || ':' || udt_name FROM information_schema.columns WHERE table_schema='public' AND table_name='orders' ORDER BY ordinal_position;\n")
        pk = self.sql("SELECT a.attname FROM pg_index i JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=ANY(i.indkey) WHERE i.indrelid='public.orders'::regclass AND i.indisprimary ORDER BY a.attnum;\n")
        if columns.splitlines() != ["id:uuid", "data:jsonb"] or pk != "id":
            raise DataError("Existing orders table differs from id UUID PRIMARY KEY, data JSONB; not modified")

    def count(self):
        return int(self.sql("SELECT count(*) FROM public.orders;\n"))

    def fetch(self, ids):
        literals = ",".join("'" + valid_uuid(uid) + "'::uuid" for uid in ids)
        if not literals:
            return {}
        output = self.sql("SELECT json_build_object('id',id::text,'doc',data) FROM public.orders WHERE id IN (" + literals + ") ORDER BY id;\n")
        result = {}
        for line in output.splitlines():
            record = parse_json(line)
            uid = valid_uuid(record["id"])
            if record["doc"].get("order_id") != uid or uid in result:
                raise DataError("PostgreSQL id differs from data.order_id or duplicate UUID")
            result[uid] = record["doc"]
        return result

    def insert(self, docs):
        stream = io.StringIO()
        stream.write("BEGIN;\nCOPY public.orders (id,data) FROM STDIN WITH (FORMAT csv);\n")
        writer = csv.writer(stream, lineterminator="\n")
        for doc in docs:
            writer.writerow((valid_uuid(doc["order_id"]), json_text(doc)))
        stream.write("\\.\nCOMMIT;\n")
        self.sql(stream.getvalue())
