// vite build 후 web/dist → lib/dashboard/static 복사.
// FastAPI 가 StaticFiles 로 serve.
import { cpSync, existsSync, rmSync, mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const dist = resolve(__dirname, '..', 'dist');
const target = resolve(__dirname, '..', '..', 'lib', 'dashboard', 'static');

if (!existsSync(dist)) {
  console.error(`dist 없음: ${dist}. 'npm run build' 먼저.`);
  process.exit(1);
}

rmSync(target, { recursive: true, force: true });
mkdirSync(target, { recursive: true });
cpSync(dist, target, { recursive: true });
console.log(`✓ ${dist} → ${target}`);
