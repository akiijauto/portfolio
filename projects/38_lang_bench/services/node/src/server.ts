// 3言語共通仕様のスコアリングAPI（TypeScript実装・HTTP層）。
// 計算ロジックは core.ts に置いてある。
//
// Node は1プロセス1スレッドなので、他言語と同じCPU割当を使い切るために
// cluster で WORKERS 個のワーカーを立てる（Python の uvicorn workers、
// Ruby の puma workers、Go の GOMAXPROCS と同じ役割）。

import cluster from 'node:cluster';
import Fastify from 'fastify';
import { ValidationError, compute } from './core.js';

const PORT = Number(process.env.PORT ?? 8000);
const WORKERS = Number(process.env.WORKERS ?? 2);

if (cluster.isPrimary && WORKERS > 1) {
  for (let i = 0; i < WORKERS; i++) cluster.fork();
  cluster.on('exit', (worker) => {
    console.error(`worker ${worker.process.pid} exited`);
  });
} else {
  let processed = 0;
  const app = Fastify({ logger: false });

  app.post('/api/v1/score', async (request, reply) => {
    try {
      const body = compute(request.body as never);
      processed += 1;
      return body;
    } catch (err) {
      if (err instanceof ValidationError || err instanceof TypeError) {
        return reply.code(400).send({ error: 'validation_failed' });
      }
      throw err;
    }
  });

  // 不正JSONは Fastify のパーサが弾く。他実装と同じ形のエラーに揃える。
  app.setErrorHandler((err, _request, reply) => {
    if (err.statusCode === 400) return reply.code(400).send({ error: 'invalid_json' });
    return reply.code(500).send({ error: 'internal' });
  });

  app.get('/healthz', async () => ({ status: 'ok', lang: 'typescript' }));
  app.get('/metrics', async () => ({ lang: 'typescript', processed, pid: process.pid }));

  app.listen({ host: '0.0.0.0', port: PORT }).catch((err) => {
    console.error(err);
    process.exit(1);
  });
}
