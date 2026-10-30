import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vite';

const DATA_DIR = path.resolve(fileURLToPath(new URL('.', import.meta.url)), '../data');
const EPISODE_DIRS = ['examples', 'episodes'];
const FILE_RE = /^[\w.-]+\.json$/;

// Sirve los episodios de ../data como /api/episodes (lista) y /api/episodes/<carpeta>/<archivo>.
function episodesApi(req, res, next) {
  const url = new URL(req.url, 'http://localhost');
  const parts = url.pathname.split('/').filter(Boolean);

  if (parts.length === 0) {
    const list = [];
    for (const dir of EPISODE_DIRS) {
      const full = path.join(DATA_DIR, dir);
      if (!fs.existsSync(full)) continue;
      for (const name of fs.readdirSync(full)) {
        if (!FILE_RE.test(name)) continue;
        const mtime = fs.statSync(path.join(full, name)).mtimeMs;
        list.push({ id: `${dir}/${name}`, dir, name, mtime });
      }
    }
    list.sort((a, b) => (a.dir === b.dir ? b.mtime - a.mtime : a.dir === 'examples' ? -1 : 1));
    res.setHeader('Content-Type', 'application/json');
    res.end(JSON.stringify(list));
    return;
  }

  const [dir, name] = parts;
  if (parts.length !== 2 || !EPISODE_DIRS.includes(dir) || !FILE_RE.test(name)) return next();
  const file = path.join(DATA_DIR, dir, name);
  if (!fs.existsSync(file)) {
    res.statusCode = 404;
    res.end('not found');
    return;
  }
  res.setHeader('Content-Type', 'application/json');
  fs.createReadStream(file).pipe(res);
}

const episodesPlugin = {
  name: 'robot-expedition-episodes',
  configureServer(server) {
    server.middlewares.use('/api/episodes', episodesApi);
  },
  configurePreviewServer(server) {
    server.middlewares.use('/api/episodes', episodesApi);
  },
};

export default defineConfig({
  plugins: [episodesPlugin],
  server: { open: true },
});
