import { createHash } from 'node:crypto';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

const [lock, destino] = process.argv.slice(2);
if (!lock || !destino) throw new Error('Se requieren el lock de Wolfi y el directorio de destino.');
const arquitectura = 'x86_64';
const base = 'https://packages.wolfi.dev/os/' + arquitectura + '/';
const carpeta = join(destino, arquitectura);
const paquetes = new Map();
for (const linea of (await readFile(lock, 'utf8')).trim().split(/\r?\n/)) {
  const datos = /^([0-9a-f]{64})  ([a-z0-9][a-z0-9._+-]*)  ([a-zA-Z0-9._+-]+)$/.exec(linea);
  if (!datos || paquetes.has(datos[2])) throw new Error('Entrada inválida o repetida en el lock de Wolfi.');
  paquetes.set(datos[2], { sha256: datos[1], version: datos[3] });
}

async function descargar(nombre) {
  const respuesta = await fetch(base + nombre);
  if (!respuesta.ok) throw new Error(nombre + ': HTTP ' + respuesta.status);
  return Buffer.from(await respuesta.arrayBuffer());
}

await mkdir(carpeta, { recursive: true });
await writeFile(join(carpeta, 'APKINDEX.tar.gz'), await descargar('APKINDEX.tar.gz'));
const solicitados = [];
for (const [nombre, { version, sha256 }] of paquetes) {
  const archivo = nombre + '-' + version + '.apk';
  const bytes = await descargar(archivo);
  if (createHash('sha256').update(bytes).digest('hex') !== sha256) {
    throw new Error('SHA-256 incorrecto para ' + archivo);
  }
  await writeFile(join(carpeta, archivo), bytes);
  solicitados.push(nombre + '=' + version);
}
await writeFile(join(destino, 'solicitados.txt'), solicitados.join('\n') + '\n');
console.log(paquetes.size + ' paquetes APK comprobados.');
