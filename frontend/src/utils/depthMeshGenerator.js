/**
 * Converts depth map images to Three.js BufferGeometry.
 * Accepts blob: URLs (already auth-fetched) or any cross-origin-accessible URL.
 */

import * as THREE from 'three';

/**
 * Load image from a URL and return its ImageData.
 * Works with blob: URLs produced by URL.createObjectURL().
 * @param {string} url - Blob URL or any accessible image URL
 * @returns {Promise<ImageData>}
 */
async function loadImageData(url) {
  return new Promise((resolve, reject) => {
    const img = new Image();

    img.onload = () => {
      const canvas = document.createElement('canvas');
      canvas.width = img.width;
      canvas.height = img.height;
      const ctx = canvas.getContext('2d');

      if (!ctx) {
        reject(new Error('Could not get canvas 2D context'));
        return;
      }

      ctx.drawImage(img, 0, 0);

      let imageData;
      try {
        imageData = ctx.getImageData(0, 0, img.width, img.height);
      } catch (e) {
        reject(new Error(`getImageData failed (CORS?): ${e.message}`));
        return;
      }

      resolve(imageData);
    };

    img.onerror = () => reject(new Error(`Failed to load image: ${url}`));

    if (url.startsWith('blob:')) {
      // same-origin object URL — canvas never tainted, no crossOrigin needed
    } else if (
      url.startsWith('/') ||
      url.startsWith('http://localhost') ||
      url.startsWith('http://127.0.0.1') ||
      url.startsWith('https://localhost') ||
      url.startsWith('https://127.0.0.1')
    ) {
      // same-origin (relative path or local dev server) — forward auth cookies
      img.crossOrigin = 'use-credentials';
    } else if (url.startsWith('http://') || url.startsWith('https://')) {
      // external cross-origin — no credentials available
      img.crossOrigin = 'anonymous';
    }
    // else: other schemes (data:, etc.) — no crossOrigin
    img.src = url;
  });
}

/**
 * Sample depth values from ImageData using bilinear interpolation,
 * resampled to the target grid resolution.
 * @param {ImageData} imageData
 * @param {number} gridSize
 * @returns {Float32Array} Normalised depth values [0, 1]
 */
function sampleDepthValues(imageData, gridSize) {
  const { width: srcW, height: srcH, data } = imageData;
  const out = new Float32Array(gridSize * gridSize);

  const getGray = (px, py) => {
    const i = (Math.min(py, srcH - 1) * srcW + Math.min(px, srcW - 1)) * 4;
    return (data[i] + data[i + 1] + data[i + 2]) / 3 / 255;
  };

  for (let gy = 0; gy < gridSize; gy++) {
    for (let gx = 0; gx < gridSize; gx++) {
      const sx = (gx / gridSize) * srcW;
      const sy = (gy / gridSize) * srcH;
      const x0 = Math.floor(sx);
      const y0 = Math.floor(sy);
      const x1 = Math.min(x0 + 1, srcW - 1);
      const y1 = Math.min(y0 + 1, srcH - 1);
      const fx = sx - x0;
      const fy = sy - y0;

      const v = (1 - fy) * ((1 - fx) * getGray(x0, y0) + fx * getGray(x1, y0)) +
                    fy  * ((1 - fx) * getGray(x0, y1) + fx * getGray(x1, y1));

      out[gy * gridSize + gx] = v;
    }
  }

  return out;
}

/**
 * Build vertex positions from a depth grid.
 * X/Z span [-1, 1], Y (height) spans [0, heightScale].
 * @param {Float32Array} depthGrid
 * @param {number} gridSize
 * @param {number} heightScale
 * @returns {Float32Array}
 */
function generateVertices(depthGrid, gridSize, heightScale) {
  const verts = new Float32Array(gridSize * gridSize * 3);
  for (let y = 0; y < gridSize; y++) {
    for (let x = 0; x < gridSize; x++) {
      const vi = (y * gridSize + x) * 3;
      verts[vi]     = (x / (gridSize - 1) - 0.5) * 2;
      verts[vi + 1] = depthGrid[y * gridSize + x] * heightScale;
      verts[vi + 2] = (y / (gridSize - 1) - 0.5) * 2;
    }
  }
  return verts;
}

/**
 * Build triangle indices for a quad grid (2 triangles per cell).
 * @param {number} gridSize
 * @returns {Uint32Array}
 */
function generateIndices(gridSize) {
  const cells = (gridSize - 1) * (gridSize - 1);
  const idx = new Uint32Array(cells * 6);
  let i = 0;
  for (let y = 0; y < gridSize - 1; y++) {
    for (let x = 0; x < gridSize - 1; x++) {
      const a = y * gridSize + x;
      const b = a + 1;
      const c = a + gridSize;
      const d = c + 1;
      idx[i++] = a; idx[i++] = b; idx[i++] = c;
      idx[i++] = b; idx[i++] = d; idx[i++] = c;
    }
  }
  return idx;
}

/**
 * Accumulate face normals per vertex, then normalise (Newell's method).
 * @param {Float32Array} verts
 * @param {Uint32Array} idx
 * @returns {Float32Array}
 */
function computeNormals(verts, idx) {
  const normals = new Float32Array(verts.length); // zero-initialised

  for (let i = 0; i < idx.length; i += 3) {
    const i0 = idx[i] * 3, i1 = idx[i + 1] * 3, i2 = idx[i + 2] * 3;

    const ax = verts[i1] - verts[i0], ay = verts[i1+1] - verts[i0+1], az = verts[i1+2] - verts[i0+2];
    const bx = verts[i2] - verts[i0], by = verts[i2+1] - verts[i0+1], bz = verts[i2+2] - verts[i0+2];

    const nx = ay * bz - az * by;
    const ny = az * bx - ax * bz;
    const nz = ax * by - ay * bx;

    for (const vi of [i0, i1, i2]) {
      normals[vi]   += nx;
      normals[vi+1] += ny;
      normals[vi+2] += nz;
    }
  }

  for (let i = 0; i < normals.length; i += 3) {
    const len = Math.sqrt(normals[i]**2 + normals[i+1]**2 + normals[i+2]**2);
    if (len > 0) {
      normals[i] /= len; normals[i+1] /= len; normals[i+2] /= len;
    } else {
      normals[i+1] = 1; // fallback: face up
    }
  }

  return normals;
}

/**
 * Create a Three.js BufferGeometry height-mapped from a depth image.
 *
 * @param {string} blobUrl   - Blob URL from URL.createObjectURL() (auth already resolved)
 * @param {number} gridSize  - Grid resolution; best as power of 2 (default 64)
 * @param {number} heightScale - Vertical exaggeration (default 0.5)
 * @returns {Promise<THREE.BufferGeometry>}
 */
export async function createDepthMeshGeometry(blobUrl, gridSize = 64, heightScale = 0.5) {
  if (!blobUrl) throw new Error('blobUrl is required');

  const safeGrid = [32, 64, 128, 256].includes(gridSize) ? gridSize : 64;
  if (safeGrid !== gridSize) console.warn(`[Mesh] gridSize ${gridSize} → using ${safeGrid}`);

  const safeHeight = (heightScale > 0 && heightScale <= 2) ? heightScale : 0.5;
  if (safeHeight !== heightScale) console.warn(`[Mesh] heightScale ${heightScale} → using ${safeHeight}`);

  console.log(`[Mesh] Loading depth map from blob URL`);
  const imageData = await loadImageData(blobUrl);
  console.log(`[Mesh] Image loaded: ${imageData.width}x${imageData.height}px`);

  const depthGrid = sampleDepthValues(imageData, safeGrid);
  console.log(`[Mesh] Depth grid sampled: ${safeGrid}x${safeGrid}`);

  const vertices = generateVertices(depthGrid, safeGrid, safeHeight);
  const indices  = generateIndices(safeGrid);
  const normals  = computeNormals(vertices, indices);

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(vertices, 3));
  geometry.setAttribute('normal',   new THREE.BufferAttribute(normals,  3));
  geometry.setIndex(new THREE.BufferAttribute(indices, 1));
  geometry.computeBoundingBox();

  console.log(`[Mesh] Geometry created: { vertices: ${vertices.length / 3}, triangles: ${indices.length / 3}, gridSize: ${safeGrid}, heightScale: ${safeHeight} }`);
  console.log(`[Mesh] Triangle count: ${indices.length / 3} (optimal: <100k)`);

  return geometry;
}

/**
 * Return geometry stats for debugging.
 * @param {THREE.BufferGeometry} geometry
 */
export function getGeometryStats(geometry) {
  if (!geometry?.attributes?.position) return null;
  return {
    vertices:    geometry.attributes.position.count,
    triangles:   geometry.index ? geometry.index.count / 3 : 0,
    hasNormals:  !!geometry.attributes.normal,
    boundingBox: geometry.boundingBox,
  };
}
