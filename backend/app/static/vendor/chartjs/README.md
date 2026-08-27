# Chart.js local (pendiente de completar en tu máquina)

Este directorio existe para alojar una copia local de Chart.js 4.4.4
(build UMD minificado), servida por FastAPI vía el mount ya existente
`app.mount("/static", StaticFiles(directory="app/static"), ...)`.

## Por qué está vacío

El entorno donde se preparó este cambio tiene el acceso de red
restringido a una lista blanca de hosts que **no incluye** cdnjs.cloudflare.com,
unpkg.com ni raw.githubusercontent.com (los tres intentos devolvieron
`403 host_not_allowed`). No se generó ni reconstruyó manualmente el
archivo minificado -eso podría introducir un archivo corrupto,
desactualizado o con licencia incorrecta sin que nadie lo note.

## Qué debes colocar aquí

Un único archivo:

```
chart.umd.min.js
```

correspondiente a **Chart.js versión 4.4.4**, build UMD minificado
-la misma versión que ya estaba referenciada por CDN en los tres
templates estadísticos, para no introducir ninguna diferencia de
comportamiento.

## Cómo obtenerlo (en tu máquina, con internet real)

Cualquiera de estas fuentes oficiales es válida:

- npm: `npm view chart.js@4.4.4 dist.tarball` y extraer `dist/chart.umd.min.js`
  del paquete, o simplemente `npm pack chart.js@4.4.4` y extraer ese archivo.
- CDN oficial (para descargar una sola vez y vendorizar, no para servir en producción):
  `https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.4/chart.umd.min.js`
- GitHub releases del proyecto Chart.js, tag `v4.4.4`, archivo `dist/chart.umd.min.js`.

## Licencia

Chart.js se distribuye bajo licencia MIT. El archivo UMD oficial ya
incluye su propio encabezado de licencia embebido en el minificado
-consérvalo tal cual viene, no lo edites ni lo quites. Si prefieres
además un archivo de licencia explícito junto al asset, copia el
`LICENSE.md` del repositorio oficial de Chart.js (tag `v4.4.4`) a:

```
app/static/vendor/chartjs/LICENSE.md
```

## Verificación después de colocar el archivo

```bash
curl -I http://localhost:8000/static/vendor/chartjs/chart.umd.min.js
# Debe responder 200, con content-type application/javascript
```

Y en el navegador, en cualquiera de las tres páginas estadísticas:

```js
typeof Chart  // debe devolver "function", no "undefined"
```

Los tres templates estadísticos ya fueron actualizados para apuntar a
`/static/vendor/chartjs/chart.umd.min.js` -no requieren ningún otro
cambio una vez que este archivo esté presente.
