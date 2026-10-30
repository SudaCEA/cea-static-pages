$ErrorActionPreference = 'Stop'
$js = Join-Path $PSScriptRoot '..\js'
Push-Location $js
try {
  npx --yes esbuild@0.25.0 `
    three-bundle-entry.js `
    --bundle `
    --format=esm `
    --target=es2022 `
    --minify `
    --legal-comments=eof `
    --banner:js="/* Generated from three-bundle-entry.js. Rebuild after changing js/vendor/three. mirror.js is not included. */" `
    --outfile=three.bundle.js
} finally {
  Pop-Location
}
