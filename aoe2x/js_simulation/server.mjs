import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";


const CONTENT_TYPES = new Map([
  [".css", "text/css; charset=utf-8"],
  [".html", "text/html; charset=utf-8"],
  [".js", "text/javascript; charset=utf-8"],
  [".mjs", "text/javascript; charset=utf-8"],
  [".json", "application/json; charset=utf-8"],
]);


function publicFile(root, pathname) {
  if (pathname === "/") return path.join(root, "viewer", "index.html");
  if (pathname === "/api/map") return path.join(root, "fixtures", "golden_map.json");
  if (pathname === "/api/formation") {
    return path.join(root, "fixtures", "golden_formation_21v21.json");
  }

  const match = pathname.match(/^\/(viewer|src)\/(.+)$/);
  if (!match) return null;
  let relative;
  try {
    relative = decodeURIComponent(match[2]);
  } catch {
    return null;
  }
  if (!relative || relative.includes("\\") || relative.split("/").includes("..")) {
    return null;
  }
  const publicRoot = path.resolve(root, match[1]);
  const candidate = path.resolve(publicRoot, relative);
  return candidate.startsWith(`${publicRoot}${path.sep}`) ? candidate : null;
}


function send(response, status, body, contentType = "text/plain; charset=utf-8") {
  response.writeHead(status, {
    "Cache-Control": "no-store",
    "Content-Length": body.byteLength,
    "Content-Type": contentType,
    "X-Content-Type-Options": "nosniff",
  });
  response.end(body);
}


export function createMapServer({ root }) {
  const resolvedRoot = path.resolve(root);
  return createServer(async (request, response) => {
    const pathname = new URL(request.url, "http://localhost").pathname;
    const file = publicFile(resolvedRoot, pathname);
    if (!file) {
      send(response, 404, Buffer.from("not found\n"));
      return;
    }

    try {
      const body = await readFile(file);
      const contentType = CONTENT_TYPES.get(path.extname(file).toLowerCase());
      if (!contentType) {
        send(response, 404, Buffer.from("not found\n"));
        return;
      }
      send(response, 200, body, contentType);
    } catch (error) {
      if (error?.code === "ENOENT" || error?.code === "EISDIR") {
        send(response, 404, Buffer.from("not found\n"));
        return;
      }
      send(response, 500, Buffer.from("server error\n"));
    }
  });
}


function parseArgs(argv) {
  const options = { host: "127.0.0.1", port: 5011 };
  for (let index = 0; index < argv.length; index += 1) {
    if (argv[index] === "--host" && argv[index + 1]) {
      options.host = argv[index += 1];
    } else if (argv[index] === "--port" && argv[index + 1]) {
      options.port = Number(argv[index += 1]);
    } else {
      throw new Error(`unknown or incomplete option: ${argv[index]}`);
    }
  }
  if (!Number.isInteger(options.port) || options.port < 0 || options.port > 65535) {
    throw new Error("--port must be an integer from 0 through 65535");
  }
  return options;
}


const isMain = process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href;
if (isMain) {
  const root = path.dirname(fileURLToPath(import.meta.url));
  const { host, port } = parseArgs(process.argv.slice(2));
  const server = createMapServer({ root });
  server.listen(port, host, () => {
    const address = server.address();
    console.log(`Golden Arena map inspector: http://${host}:${address.port}`);
  });
}
