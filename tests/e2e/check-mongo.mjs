// Read-only check of the texts the local SMSTunnel API accepted (test database only).
//   node tests/e2e/check-mongo.mjs "<text to look for>" [minutes back, default 30]
// Prints, for each matching text: when, to, status, and the start of the text. Never writes anything.
import { createRequire } from 'node:module';

const require = createRequire(process.env.SMSTUNNEL_SERVER_PACKAGE || 'D:/ANDROID/SMSserver/package.json');
const { MongoClient } = require('mongodb');

const needle = process.argv[2] || 'Odoo';
const minutes = Number(process.argv[3] || 30);
const url = process.env.SMSTUNNEL_TEST_MONGO || 'mongodb://127.0.0.1:27018/smstunnel_app_dev';

const client = new MongoClient(url, { readPreference: 'secondaryPreferred' });
try {
  await client.connect();
  const since = new Date(Date.now() - minutes * 60_000);
  const escaped = needle.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const rows = await client.db().collection('messages')
    .find({ createdAt: { $gte: since }, message: { $regex: escaped } })
    .project({ phoneNumber: 1, message: 1, status: 1, createdAt: 1, source: 1 })
    .sort({ createdAt: 1 })
    .toArray();
  for (const row of rows) {
    console.log([row.createdAt.toISOString(), row.phoneNumber, row.status, row.source || '-',
      JSON.stringify(String(row.message).slice(0, 90))].join('  '));
  }
  console.log(`${rows.length} text(s) matching ${JSON.stringify(needle)} in the last ${minutes} min`);
} finally {
  await client.close();
}
