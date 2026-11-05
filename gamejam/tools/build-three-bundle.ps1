$ErrorActionPreference = 'Stop'
$three = Join-Path $PSScriptRoot '..\libs\three'
Push-Location $three
try {
  npx --yes esbuild@0.25.0 `
    src/three-bundle-entry.js `
    --bundle `
    --format=esm `
    --target=es2022 `
    --minify `
    --legal-comments=eof `
    --banner:js="/* Generated from libs/three/src/three-bundle-entry.js. Rebuild after changing libs/three/vendor/three. mirror.js is not included. */" `
    --outfile=three.bundle.js
} finally {
  Pop-Location
}
