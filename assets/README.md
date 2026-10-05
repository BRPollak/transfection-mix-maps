# App icon

A teal tile with a simple six-well plate and one light-purple well, matching the app palette.

- `mix-maps-icon.png`: 256 px transparent PNG used by the app header and browser tab.
- `mix-maps-icon-1024.png`: 1024 px transparent PNG for reuse.
- `mix-maps.icns`: multiresolution macOS icon for Finder, aliases, and the Dock.
- `mix-maps-icon-corrected.png`: corrected source artwork, with the dark blur above the plate removed; used for all current exports.
- `mix-maps-icon-original.png`: original generated artwork, retained as an archive; not used by the app.

Created with the built-in image generation tool. PNG size exports use macOS `sips`; the ICNS uses `iconutil` with standard 16–1024 px representations. Transparency is preserved.

The macOS builder copies the ICNS into the app bundle and sets `CFBundleIconFile`. Rebuild the app to apply the icon to packaged copies.

## Correction prompt

Edited with the built-in image generation tool, then refreshed both PNG exports and the ICNS file.

```text
Use case: precise-object-edit
Input image: the existing Transfection Mix Maps app icon; edit target.
Fix the unwanted dark blurry smudge near the top of the teal tile. Remove ALL cloudy shading, gradients, texture, spots, and lighting from the colored shapes, particularly the dark horizontal blurry area at the upper center. The entire teal background tile must be one uniform solid flat teal #237D70, including above the white plate. Fill each of the five teal circular wells with that same uniform solid teal. White plate is flat solid #FAFBF8, purple well is flat solid #D8C5EC.
Keep the existing design, positions, proportions, six circles in two rows of three, lower-right purple circle, rounded corners, square canvas, transparent exterior padding, and shape geometry unchanged. Crisp antialiased edges only. Do not introduce any shadow, lighting, depth, texture or tonal variation anywhere inside a shape. No text or extra elements. Preserve actual transparency outside the tile.
Output just the corrected app icon.
```

## Generation prompt

```text
Use case: logo-brand
Asset type: a single finished application icon for Transfection Mix Maps, a laboratory plate-layout app; displayed in the app, browser favicon, Finder and macOS Dock.
Primary request: a very simple, crisp geometric icon, recognizable at 32 pixels.
Subject: one stylized six-well laboratory plate viewed straight from above. A solid warm-white horizontal rounded rectangle, with exactly six large circular wells evenly spaced in two rows of three. Five wells are teal, matching the background; the bottom-right well is light purple (#D8C5EC). No extra details or marks.
Composition: square 1024 by 1024 canvas. One large solid teal (#237D70) rounded-square tile, centered with about 7 percent transparent padding on each side and smooth macOS-like rounded corners. The white plate is centered on the tile, width about 67 percent of the tile, height about 48 percent of the tile. Generous, balanced whitespace. Large wells; bold simple forms that survive reduction to a favicon.
Style: extremely minimal flat vector-like graphic, perfectly symmetric geometry, smooth crisp edges. Use only teal, warm white (#FAFBF8), and light purple. Flat colors, no gradients, no lighting, no texture, no shadows, no perspective.
Constraints: ONE icon only, no mockup or presentation sheet. No text, no letters, no pipette, no molecules, no borders around the tile, no watermark. Outside the rounded-square tile must be genuinely transparent.
```
